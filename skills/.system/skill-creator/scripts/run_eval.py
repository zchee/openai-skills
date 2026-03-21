#!/usr/bin/env python3
"""Run trigger evaluation for a skill description.

Tests whether a skill's description causes Claude to trigger (read the skill)
for a set of queries. Outputs results as JSON.
"""

import argparse
import json
import os
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.utils import parse_skill_md

STDERR_CAPTURE_LIMIT = 4096
MAX_WARNING_CONTEXTS = 5


def _append_limited(buffer: bytearray, chunk: bytes, limit: int) -> None:
    """Append bytes while retaining only the last `limit` bytes."""
    if not chunk:
        return
    buffer.extend(chunk)
    if len(buffer) > limit:
        del buffer[:-limit]


def _stderr_snippet(buffer: bytearray, max_chars: int = 300) -> str:
    """Return a compact single-line stderr snippet for warnings."""
    if not buffer:
        return ""
    text = bytes(buffer).decode("utf-8", errors="replace")
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[:max_chars] + "..."
    return text


def _query_preview(query: str, max_chars: int = 80) -> str:
    """Return a compact query preview for warning contexts."""
    if len(query) <= max_chars:
        return query
    return query[:max_chars]


def _normalize_warning_payload(warning: object) -> dict[str, object]:
    """Normalize warning payload shape for compaction and display."""
    if isinstance(warning, str):
        return {
            "kind": "legacy",
            "timeout": None,
            "return_code": None,
            "stderr_snippet": "",
            "detail": "",
            "message": warning,
        }

    if isinstance(warning, dict):
        kind = str(warning.get("kind", "unknown"))
        timeout = warning.get("timeout")
        return_code = warning.get("return_code")
        stderr_snippet = str(warning.get("stderr_snippet", ""))
        detail = str(warning.get("detail", ""))
        message = str(warning.get("message", ""))
        return {
            "kind": kind,
            "timeout": timeout if isinstance(timeout, int) else None,
            "return_code": return_code if isinstance(return_code, int) else None,
            "stderr_snippet": stderr_snippet,
            "detail": detail,
            "message": message,
        }

    return {
        "kind": "unknown",
        "timeout": None,
        "return_code": None,
        "stderr_snippet": "",
        "detail": "",
        "message": repr(warning),
    }


def _warning_compaction_key(payload: dict[str, object]) -> tuple[str, str, str, str, str, str]:
    """Build a stable grouping key that excludes query/run context."""
    return (
        str(payload.get("kind", "")),
        "" if payload.get("timeout") is None else str(payload["timeout"]),
        "" if payload.get("return_code") is None else str(payload["return_code"]),
        str(payload.get("stderr_snippet", "")),
        str(payload.get("detail", "")),
        str(payload.get("message", "")),
    )


def _warning_summary_line(payload: dict[str, object], count: int) -> str:
    """Render a compact warning summary for a grouped warning class."""
    occurrences = "occurrence" if count == 1 else "occurrences"
    kind = str(payload.get("kind", "unknown"))
    stderr_snippet = str(payload.get("stderr_snippet", ""))
    detail = str(payload.get("detail", ""))
    message = str(payload.get("message", ""))

    if kind == "timeout":
        timeout = payload.get("timeout")
        timeout_text = f"{timeout}s" if isinstance(timeout, int) else "unknown timeout"
        summary = f"Warning: claude -p timed out after {timeout_text} ({count} {occurrences})"
        if stderr_snippet:
            summary += f": {stderr_snippet}"
        return summary

    if kind == "exit":
        return_code = payload.get("return_code")
        code_text = str(return_code) if isinstance(return_code, int) else "unknown"
        summary = f"Warning: claude -p exited {code_text} ({count} {occurrences})"
        if stderr_snippet:
            summary += f": {stderr_snippet}"
        return summary

    if kind == "worker_exception":
        summary = f"Warning: query execution failed ({count} {occurrences})"
        if detail:
            summary += f": {detail}"
        return summary

    if kind == "legacy":
        if message:
            return f"Warning: repeated worker warning ({count} {occurrences}): {message}"
        return f"Warning: repeated worker warning ({count} {occurrences})."

    if message:
        return f"Warning: {message} ({count} {occurrences})"
    return f"Warning: unclassified worker warning ({count} {occurrences})."


def format_compacted_warning_lines(
    warning_records: list[dict[str, object]],
    max_contexts: int = MAX_WARNING_CONTEXTS,
) -> list[str]:
    """Group warning records and return deterministic compact stderr lines."""
    if not warning_records:
        return []
    if max_contexts < 1:
        raise ValueError("max_contexts must be >= 1")

    normalized_records: list[tuple[int, int, str, dict[str, object]]] = []
    for record in warning_records:
        item_idx = int(record.get("item_idx", -1))
        run_idx = int(record.get("run_idx", -1))
        query = str(record.get("query_preview", ""))
        payload = _normalize_warning_payload(record.get("warning"))
        normalized_records.append((item_idx, run_idx, query, payload))

    normalized_records.sort(key=lambda rec: (rec[0], rec[1], rec[2]))

    grouped_contexts: dict[tuple[str, str, str, str, str, str], list[tuple[int, int, str]]] = {}
    grouped_payloads: dict[tuple[str, str, str, str, str, str], dict[str, object]] = {}
    for item_idx, run_idx, query, payload in normalized_records:
        key = _warning_compaction_key(payload)
        grouped_payloads[key] = payload
        grouped_contexts.setdefault(key, []).append((item_idx, run_idx, query))

    lines: list[str] = []
    for key in sorted(grouped_contexts):
        payload = grouped_payloads[key]
        contexts = grouped_contexts[key]
        lines.append(_warning_summary_line(payload, len(contexts)))

        sampled_contexts = contexts[:max_contexts]
        rendered_contexts = [
            f"item={item_idx} run={run_idx} query={query!r}"
            for item_idx, run_idx, query in sampled_contexts
        ]
        if len(contexts) > max_contexts:
            rendered_contexts.append(f"(+{len(contexts) - max_contexts} more)")
        lines.append(f"  contexts: {'; '.join(rendered_contexts)}")

    return lines


def find_project_root() -> Path:
    """Find the project root by walking up from cwd looking for .claude/.

    Mimics how Claude Code discovers its project root, so the command file
    we create ends up where claude -p will look for it.
    """
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return current


def run_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
    warn_timeouts: bool = False,
) -> tuple[bool, dict[str, object] | None]:
    """Run one query and return (triggered, optional warning payload).

    Creates a command file in .claude/commands/ so it appears in Claude's
    available_skills list, then runs `claude -p` with the raw query.
    Uses --include-partial-messages to detect triggering early from
    stream events (content_block_start) rather than waiting for the
    full assistant message, which only arrives after tool execution.
    """
    unique_id = uuid.uuid4().hex[:8]
    clean_name = f"{skill_name}-skill-{unique_id}"
    project_commands_dir = Path(project_root) / ".claude" / "commands"
    command_file = project_commands_dir / f"{clean_name}.md"

    try:
        project_commands_dir.mkdir(parents=True, exist_ok=True)
        # Use YAML block scalar to avoid breaking on quotes in description
        indented_desc = "\n  ".join(skill_description.split("\n"))
        command_content = (
            f"---\n"
            f"description: |\n"
            f"  {indented_desc}\n"
            f"---\n\n"
            f"# {skill_name}\n\n"
            f"This skill handles: {skill_description}\n"
        )
        command_file.write_text(command_content)

        cmd = [
            "claude",
            "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        # Remove CLAUDECODE env var to allow nesting claude -p inside a
        # Claude Code session. The guard is for interactive terminal conflicts;
        # programmatic subprocess usage is safe.
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            env=env,
        )

        triggered = False
        outcome: bool | None = None
        start_time = time.time()
        buffer = ""
        stderr_buffer = bytearray()
        return_code: int | None = None
        timed_out = False
        # Track state for stream event detection
        pending_tool_name = None
        accumulated_json = ""

        try:
            while time.time() - start_time < timeout and outcome is None:
                if process.poll() is not None:
                    return_code = process.returncode
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    remaining_stderr = process.stderr.read()
                    _append_limited(stderr_buffer, remaining_stderr, STDERR_CAPTURE_LIMIT)
                    break

                ready, _, _ = select.select([process.stdout, process.stderr], [], [], 1.0)
                if not ready:
                    continue

                if process.stdout in ready:
                    chunk = os.read(process.stdout.fileno(), 8192)
                    if chunk:
                        buffer += chunk.decode("utf-8", errors="replace")

                if process.stderr in ready:
                    err_chunk = os.read(process.stderr.fileno(), 8192)
                    _append_limited(stderr_buffer, err_chunk, STDERR_CAPTURE_LIMIT)

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Early detection via stream events
                    if event.get("type") == "stream_event":
                        se = event.get("event", {})
                        se_type = se.get("type", "")

                        if se_type == "content_block_start":
                            cb = se.get("content_block", {})
                            if cb.get("type") == "tool_use":
                                tool_name = cb.get("name", "")
                                if tool_name in ("Skill", "Read"):
                                    pending_tool_name = tool_name
                                    accumulated_json = ""
                                else:
                                    outcome = False
                                    break

                        elif se_type == "content_block_delta" and pending_tool_name:
                            delta = se.get("delta", {})
                            if delta.get("type") == "input_json_delta":
                                accumulated_json += delta.get("partial_json", "")
                                if clean_name in accumulated_json:
                                    outcome = True
                                    break

                        elif se_type in ("content_block_stop", "message_stop"):
                            if pending_tool_name:
                                outcome = clean_name in accumulated_json
                                break
                            if se_type == "message_stop":
                                outcome = False
                                break

                    # Fallback: full assistant message
                    elif event.get("type") == "assistant":
                        message = event.get("message", {})
                        for content_item in message.get("content", []):
                            if content_item.get("type") != "tool_use":
                                continue
                            tool_name = content_item.get("name", "")
                            tool_input = content_item.get("input", {})
                            if tool_name == "Skill" and clean_name in tool_input.get("skill", ""):
                                triggered = True
                            elif tool_name == "Read" and clean_name in tool_input.get("file_path", ""):
                                triggered = True
                            outcome = triggered
                            break

                    elif event.get("type") == "result":
                        outcome = triggered
                        break

                if outcome is not None:
                    break

            timed_out = outcome is None and (time.time() - start_time) >= timeout
        finally:
            # Clean up process on any exit path (return, exception, timeout)
            if process.poll() is not None and return_code is None:
                return_code = process.returncode
            if process.poll() is None:
                process.kill()
                process.wait()

        if outcome is None:
            outcome = triggered

        # Surface useful stderr diagnostics for failed/non-triggered runs.
        warn_on_timeout = warn_timeouts and timed_out
        warn_on_exit = return_code not in (None, 0)
        warning_payload: dict[str, object] | None = None
        if not outcome and (warn_on_timeout or warn_on_exit):
            snippet = _stderr_snippet(stderr_buffer)
            if warn_on_timeout:
                warning_payload = {
                    "kind": "timeout",
                    "timeout": timeout,
                    "return_code": None,
                    "stderr_snippet": snippet,
                    "detail": "",
                    "message": "",
                }
            else:
                warning_payload = {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": return_code,
                    "stderr_snippet": snippet,
                    "detail": "",
                    "message": "",
                }

        return outcome, warning_payload
    finally:
        if command_file.exists():
            command_file.unlink()


def run_eval(
    eval_set: list[dict],
    skill_name: str,
    description: str,
    num_workers: int,
    timeout: int,
    project_root: Path,
    runs_per_query: int = 1,
    trigger_threshold: float = 0.5,
    model: str | None = None,
    warn_timeouts: bool = False,
) -> dict:
    """Run the full eval set and return results."""
    if runs_per_query < 1:
        raise ValueError("runs_per_query must be >= 1")

    results = []

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        future_to_info = {}
        query_triggers: dict[int, list[bool]] = {}
        for item_idx, item in enumerate(eval_set):
            query_triggers[item_idx] = []
            for run_idx in range(runs_per_query):
                future = executor.submit(
                    run_single_query,
                    item["query"],
                    skill_name,
                    description,
                    timeout,
                    str(project_root),
                    model,
                    warn_timeouts,
                )
                future_to_info[future] = (item_idx, run_idx)

        warning_records: list[dict[str, object]] = []
        for future in as_completed(future_to_info):
            item_idx, run_idx = future_to_info[future]
            try:
                future_result = future.result()
                if isinstance(future_result, tuple):
                    triggered, warning_payload = future_result
                else:
                    triggered = bool(future_result)
                    warning_payload = None
                query_triggers[item_idx].append(triggered)
                if warning_payload:
                    warning_records.append(
                        {
                            "item_idx": item_idx,
                            "run_idx": run_idx,
                            "query_preview": _query_preview(eval_set[item_idx]["query"]),
                            "warning": warning_payload,
                        }
                    )
            except Exception as e:
                warning_records.append(
                    {
                        "item_idx": item_idx,
                        "run_idx": run_idx,
                        "query_preview": _query_preview(eval_set[item_idx]["query"]),
                        "warning": {
                            "kind": "worker_exception",
                            "timeout": None,
                            "return_code": None,
                            "stderr_snippet": "",
                            "detail": str(e),
                            "message": "",
                        },
                    }
                )
                query_triggers[item_idx].append(False)

        # Emit compacted worker warnings from the parent process.
        for line in format_compacted_warning_lines(warning_records):
            print(line, file=sys.stderr)

    for item_idx, item in enumerate(eval_set):
        triggers = query_triggers[item_idx]
        if not triggers:
            # Should only happen if runs_per_query is changed at runtime.
            triggers = [False]

        trigger_rate = sum(triggers) / len(triggers)
        should_trigger = item["should_trigger"]
        if should_trigger:
            did_pass = trigger_rate >= trigger_threshold
        else:
            did_pass = trigger_rate < trigger_threshold
        result_item = {
            "query": item["query"],
            "should_trigger": should_trigger,
            "trigger_rate": trigger_rate,
            "triggers": sum(triggers),
            "runs": len(triggers),
            "pass": did_pass,
        }
        if "id" in item:
            result_item["id"] = item["id"]
        results.append(result_item)

    passed = sum(1 for r in results if r["pass"])
    total = len(results)

    return {
        "skill_name": skill_name,
        "description": description,
        "results": results,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run trigger evaluation for a skill description")
    parser.add_argument("--eval-set", required=True, help="Path to eval set JSON file")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override description to test")
    parser.add_argument("--num-workers", type=int, default=10, help="Number of parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query in seconds")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Number of runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger rate threshold")
    parser.add_argument("--model", default=None, help="Model to use for claude -p (default: user's configured model)")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument(
        "--warn-timeouts",
        action="store_true",
        help="Warn when a query times out (non-zero subprocess exits always warn)",
    )
    args = parser.parse_args()

    if args.num_workers < 1:
        print("Error: --num-workers must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.runs_per_query < 1:
        print("Error: --runs-per-query must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.timeout <= 0:
        print("Error: --timeout must be > 0", file=sys.stderr)
        sys.exit(1)

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)

    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        sys.exit(1)

    name, original_description, content = parse_skill_md(skill_path)
    description = args.description or original_description
    project_root = find_project_root()

    if args.verbose:
        print(f"Evaluating: {description}", file=sys.stderr)

    output = run_eval(
        eval_set=eval_set,
        skill_name=name,
        description=description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        project_root=project_root,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        model=args.model,
        warn_timeouts=args.warn_timeouts,
    )

    if args.verbose:
        summary = output["summary"]
        print(f"Results: {summary['passed']}/{summary['total']} passed", file=sys.stderr)
        for r in output["results"]:
            status = "PASS" if r["pass"] else "FAIL"
            rate_str = f"{r['triggers']}/{r['runs']}"
            print(f"  [{status}] rate={rate_str} expected={r['should_trigger']}: {r['query'][:70]}", file=sys.stderr)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
