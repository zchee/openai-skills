import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.run_eval import format_compacted_warning_lines


class FormatCompactedWarningLinesTests(unittest.TestCase):
    def test_groups_identical_exit_warnings(self) -> None:
        records = [
            {
                "item_idx": 2,
                "run_idx": 0,
                "query_preview": "charlie",
                "warning": {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": 42,
                    "stderr_snippet": "boom",
                    "detail": "",
                    "message": "",
                },
            },
            {
                "item_idx": 0,
                "run_idx": 1,
                "query_preview": "alpha",
                "warning": {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": 42,
                    "stderr_snippet": "boom",
                    "detail": "",
                    "message": "",
                },
            },
            {
                "item_idx": 1,
                "run_idx": 2,
                "query_preview": "bravo",
                "warning": {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": 42,
                    "stderr_snippet": "boom",
                    "detail": "",
                    "message": "",
                },
            },
        ]

        lines = format_compacted_warning_lines(records, max_contexts=10)
        self.assertEqual(2, len(lines))
        self.assertEqual("Warning: claude -p exited 42 (3 occurrences): boom", lines[0])
        self.assertEqual(
            "  contexts: item=0 run=1 query='alpha'; item=1 run=2 query='bravo'; item=2 run=0 query='charlie'",
            lines[1],
        )

    def test_mixed_warning_classes_have_deterministic_order(self) -> None:
        records = [
            {
                "item_idx": 3,
                "run_idx": 0,
                "query_preview": "q3",
                "warning": {
                    "kind": "worker_exception",
                    "timeout": None,
                    "return_code": None,
                    "stderr_snippet": "",
                    "detail": "boom",
                    "message": "",
                },
            },
            {
                "item_idx": 2,
                "run_idx": 0,
                "query_preview": "q2",
                "warning": {
                    "kind": "timeout",
                    "timeout": 30,
                    "return_code": None,
                    "stderr_snippet": "",
                    "detail": "",
                    "message": "",
                },
            },
            {
                "item_idx": 1,
                "run_idx": 0,
                "query_preview": "q1",
                "warning": {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": 2,
                    "stderr_snippet": "err two",
                    "detail": "",
                    "message": "",
                },
            },
            {
                "item_idx": 0,
                "run_idx": 0,
                "query_preview": "q0",
                "warning": {
                    "kind": "exit",
                    "timeout": None,
                    "return_code": 1,
                    "stderr_snippet": "err one",
                    "detail": "",
                    "message": "",
                },
            },
        ]

        lines = format_compacted_warning_lines(records, max_contexts=5)
        summary_lines = lines[0::2]
        self.assertEqual(
            [
                "Warning: claude -p exited 1 (1 occurrence): err one",
                "Warning: claude -p exited 2 (1 occurrence): err two",
                "Warning: claude -p timed out after 30s (1 occurrence)",
                "Warning: query execution failed (1 occurrence): boom",
            ],
            summary_lines,
        )

    def test_contexts_are_truncated_with_count_suffix(self) -> None:
        records = []
        for idx in range(7):
            records.append(
                {
                    "item_idx": idx,
                    "run_idx": 0,
                    "query_preview": f"q{idx}",
                    "warning": {
                        "kind": "timeout",
                        "timeout": 15,
                        "return_code": None,
                        "stderr_snippet": "slow response",
                        "detail": "",
                        "message": "",
                    },
                }
            )

        lines = format_compacted_warning_lines(records, max_contexts=3)
        self.assertEqual("Warning: claude -p timed out after 15s (7 occurrences): slow response", lines[0])
        self.assertEqual(
            "  contexts: item=0 run=0 query='q0'; item=1 run=0 query='q1'; item=2 run=0 query='q2'; (+4 more)",
            lines[1],
        )

    def test_legacy_string_warnings_are_compacted(self) -> None:
        records = [
            {
                "item_idx": 1,
                "run_idx": 1,
                "query_preview": "beta",
                "warning": "Warning: old format message.",
            },
            {
                "item_idx": 0,
                "run_idx": 0,
                "query_preview": "alpha",
                "warning": "Warning: old format message.",
            },
        ]

        lines = format_compacted_warning_lines(records, max_contexts=5)
        self.assertEqual(
            "Warning: repeated worker warning (2 occurrences): Warning: old format message.",
            lines[0],
        )
        self.assertEqual(
            "  contexts: item=0 run=0 query='alpha'; item=1 run=1 query='beta'",
            lines[1],
        )

    def test_empty_warning_records_return_no_lines(self) -> None:
        self.assertEqual([], format_compacted_warning_lines([]))


if __name__ == "__main__":
    unittest.main()
