---
name: skill-creator
description: Guide for creating effective skills, improving existing skills, and evaluating skill quality. Use this skill when users want to create or update a skill, design or run realistic test cases, compare baseline and candidate outputs, iterate from feedback, or optimize trigger descriptions for better routing.
metadata:
  short-description: Create, evaluate, or improve a skill
---

# Skill Creator

This skill provides guidance for creating effective skills.

## About Skills

Skills are modular, self-contained folders that extend Codex's capabilities by providing
specialized knowledge, workflows, and tools. Think of them as "onboarding guides" for specific
domains or tasks—they transform Codex from a general-purpose agent into a specialized agent
equipped with procedural knowledge that no model can fully possess.

### What Skills Provide

1. Specialized workflows - Multi-step procedures for specific domains
2. Tool integrations - Instructions for working with specific file formats or APIs
3. Domain expertise - Company-specific knowledge, schemas, business logic
4. Bundled resources - Scripts, references, and assets for complex and repetitive tasks

## Communicating with the User

Match terminology to user fluency and avoid unexplained jargon.

1. Use plain language by default.
2. Define technical terms briefly on first use when confidence is low.
3. Ask fewer, higher-signal questions per turn.
4. Confirm assumptions before moving to implementation when requirements are ambiguous.

## Core Principles

### Concise is Key

The context window is a public good. Skills share the context window with everything else Codex needs: system prompt, conversation history, other Skills' metadata, and the actual user request.

**Default assumption: Codex is already very smart.** Only add context Codex doesn't already have. Challenge each piece of information: "Does Codex really need this explanation?" and "Does this paragraph justify its token cost?"

Prefer concise examples over verbose explanations.

### Set Appropriate Degrees of Freedom

Match the level of specificity to the task's fragility and variability:

**High freedom (text-based instructions)**: Use when multiple approaches are valid, decisions depend on context, or heuristics guide the approach.

**Medium freedom (pseudocode or scripts with parameters)**: Use when a preferred pattern exists, some variation is acceptable, or configuration affects behavior.

**Low freedom (specific scripts, few parameters)**: Use when operations are fragile and error-prone, consistency is critical, or a specific sequence must be followed.

Think of Codex as exploring a path: a narrow bridge with cliffs needs specific guardrails (low freedom), while an open field allows many routes (high freedom).

### Principle of Lack of Surprise

Keep skill behavior aligned with declared purpose and user intent.

1. Do not create skills that facilitate unauthorized access, malware, stealth exfiltration, or deceptive behavior.
2. Ensure instructions and bundled resources match the frontmatter description.
3. If intent is ambiguous and risk-sensitive, pause and clarify constraints before drafting.

### Anatomy of a Skill

Every skill consists of a required SKILL.md file and optional bundled resources:

```
skill-name/
├── SKILL.md (required)
│   ├── YAML frontmatter metadata (required)
│   │   ├── name: (required)
│   │   └── description: (required)
│   └── Markdown instructions (required)
├── agents/ (recommended)
│   └── openai.yaml - UI metadata for skill lists and chips
└── Bundled Resources (optional)
    ├── scripts/          - Executable code (Python/Bash/etc.)
    ├── references/       - Documentation intended to be loaded into context as needed
    └── assets/           - Files used in output (templates, icons, fonts, etc.)
```

#### SKILL.md (required)

Every SKILL.md consists of:

- **Frontmatter** (YAML): Contains `name` and `description` fields. These are the only fields that Codex reads to determine when the skill gets used, thus it is very important to be clear and comprehensive in describing what the skill is, and when it should be used.
- **Body** (Markdown): Instructions and guidance for using the skill. Only loaded AFTER the skill triggers (if at all).

#### Agents metadata (recommended)

- UI-facing metadata for skill lists and chips
- Read references/openai_yaml.md before generating values and follow its descriptions and constraints
- Create: human-facing `display_name`, `short_description`, and `default_prompt` by reading the skill
- Generate deterministically by passing the values as `--interface key=value` to `scripts/generate_openai_yaml.py` or `scripts/init_skill.py`
- On updates: validate `agents/openai.yaml` still matches SKILL.md; regenerate if stale
- Only include other optional interface fields (icons, brand color) if explicitly provided
- See references/openai_yaml.md for field definitions and examples

#### Bundled Resources (optional)

##### Scripts (`scripts/`)

Executable code (Python/Bash/etc.) for tasks that require deterministic reliability or are repeatedly rewritten.

- **When to include**: When the same code is being rewritten repeatedly or deterministic reliability is needed
- **Example**: `scripts/rotate_pdf.py` for PDF rotation tasks
- **Benefits**: Token efficient, deterministic, may be executed without loading into context
- **Note**: Scripts may still need to be read by Codex for patching or environment-specific adjustments

##### References (`references/`)

Documentation and reference material intended to be loaded as needed into context to inform Codex's process and thinking.

- **When to include**: For documentation that Codex should reference while working
- **Examples**: `references/finance.md` for financial schemas, `references/mnda.md` for company NDA template, `references/policies.md` for company policies, `references/api_docs.md` for API specifications
- **Use cases**: Database schemas, API documentation, domain knowledge, company policies, detailed workflow guides
- **Benefits**: Keeps SKILL.md lean, loaded only when Codex determines it's needed
- **Best practice**: If files are large (>10k words), include grep search patterns in SKILL.md
- **Avoid duplication**: Information should live in either SKILL.md or references files, not both. Prefer references files for detailed information unless it's truly core to the skill—this keeps SKILL.md lean while making information discoverable without hogging the context window. Keep only essential procedural instructions and workflow guidance in SKILL.md; move detailed reference material, schemas, and examples to references files.

##### Assets (`assets/`)

Files not intended to be loaded into context, but rather used within the output Codex produces.

- **When to include**: When the skill needs files that will be used in the final output
- **Examples**: `assets/logo.png` for brand assets, `assets/slides.pptx` for PowerPoint templates, `assets/frontend-template/` for HTML/React boilerplate, `assets/font.ttf` for typography
- **Use cases**: Templates, images, icons, boilerplate code, fonts, sample documents that get copied or modified
- **Benefits**: Separates output resources from documentation, enables Codex to use files without loading them into context

#### What to Not Include in a Skill

A skill should only contain essential files that directly support its functionality. Do NOT create extraneous documentation or auxiliary files, including:

- README.md
- INSTALLATION_GUIDE.md
- QUICK_REFERENCE.md
- CHANGELOG.md
- etc.

The skill should only contain the information needed for an AI agent to do the job at hand. It should not contain auxiliary context about the process that went into creating it, setup and testing procedures, user-facing documentation, etc. Creating additional documentation files just adds clutter and confusion.

### Progressive Disclosure Design Principle

Skills use a three-level loading system to manage context efficiently:

1. **Metadata (name + description)** - Always in context (~100 words)
2. **SKILL.md body** - When skill triggers (<5k words)
3. **Bundled resources** - As needed by Codex (Unlimited because scripts can be executed without reading into context window)

#### Progressive Disclosure Patterns

Keep SKILL.md body to the essentials and under 500 lines to minimize context bloat. Split content into separate files when approaching this limit. When splitting out content into other files, it is very important to reference them from SKILL.md and describe clearly when to read them, to ensure the reader of the skill knows they exist and when to use them.

**Key principle:** When a skill supports multiple variations, frameworks, or options, keep only the core workflow and selection guidance in SKILL.md. Move variant-specific details (patterns, examples, configuration) into separate reference files.

**Pattern 1: High-level guide with references**

```markdown
# PDF Processing

## Quick start

Extract text with pdfplumber:
[code example]

## Advanced features

- **Form filling**: See [FORMS.md](FORMS.md) for complete guide
- **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
- **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
```

Codex loads FORMS.md, REFERENCE.md, or EXAMPLES.md only when needed.

**Pattern 2: Domain-specific organization**

For Skills with multiple domains, organize content by domain to avoid loading irrelevant context:

```
bigquery-skill/
├── SKILL.md (overview and navigation)
└── reference/
    ├── finance.md (revenue, billing metrics)
    ├── sales.md (opportunities, pipeline)
    ├── product.md (API usage, features)
    └── marketing.md (campaigns, attribution)
```

When a user asks about sales metrics, Codex only reads sales.md.

Similarly, for skills supporting multiple frameworks or variants, organize by variant:

```
cloud-deploy/
├── SKILL.md (workflow + provider selection)
└── references/
    ├── aws.md (AWS deployment patterns)
    ├── gcp.md (GCP deployment patterns)
    └── azure.md (Azure deployment patterns)
```

When the user chooses AWS, Codex only reads aws.md.

**Pattern 3: Conditional details**

Show basic content, link to advanced content:

```markdown
# DOCX Processing

## Creating documents

Use docx-js for new documents. See [DOCX-JS.md](DOCX-JS.md).

## Editing documents

For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

Codex reads REDLINING.md or OOXML.md only when the user needs those features.

**Important guidelines:**

- **Avoid deeply nested references** - Keep references one level deep from SKILL.md. All reference files should link directly from SKILL.md.
- **Structure longer reference files** - For files longer than 100 lines, include a table of contents at the top so Codex can see the full scope when previewing.

## Skill Creation Process

Skill creation involves these steps:

1. Capture intent with concrete examples
2. Plan reusable skill contents (scripts, references, assets)
3. Initialize the skill (run init_skill.py)
4. Edit the skill (implement resources and write SKILL.md)
5. Validate the skill (run quick_validate.py)
6. Evaluate test cases with a baseline
7. Improve the skill from evidence
8. Optimize the trigger description (optional)
9. Communicate iteration outcomes (optional)

Follow these steps in order, skipping only if there is a clear reason why they are not applicable.

### Choose the Working Stage

Start by identifying where the user is in the lifecycle: intent discovery, draft writing, evaluation, improvement, or trigger tuning.

1. Enter at the highest-value stage immediately.
2. Backfill prerequisites only when a missing input blocks progress.
3. Offer both paths when helpful:
   - Quick iteration: minimal eval set for fast feedback.
   - Full evaluation: broader coverage with baseline comparison and stronger evidence.

### Skill Naming

- Use lowercase letters, digits, and hyphens only; normalize user-provided titles to hyphen-case (e.g., "Plan Mode" -> `plan-mode`).
- When generating names, generate a name under 64 characters (letters, digits, hyphens).
- Prefer short, verb-led phrases that describe the action.
- Namespace by tool when it improves clarity or triggering (e.g., `gh-address-comments`, `linear-address-issue`).
- Name the skill folder exactly after the skill name.

### Step 1: Capture Intent with Concrete Examples

Skip this step only when the skill's usage patterns are already clearly understood. It remains valuable even when working with an existing skill.

To create an effective skill, clearly understand concrete examples of how the skill will be used. This understanding can come from either direct user examples or generated examples that are validated with user feedback.

Before asking questions, extract what is already known from conversation history and files: tools used, sequence of actions, corrections, and expected output shape.

For example, when building an image-editor skill, relevant questions include:

- "What functionality should the image-editor skill support? Editing, rotating, anything else?"
- "Can you give some examples of how this skill would be used?"
- "I can imagine users asking for things like 'Remove the red-eye from this image' or 'Rotate this image'. Are there other ways you imagine this skill being used?"
- "What would a user say that should trigger this skill?"

To avoid overwhelming users, avoid asking too many questions in a single message. Start with the most important questions and follow up as needed for better effectiveness.

Conclude this step when there is a clear sense of the functionality the skill should support.

Before moving to Step 2, confirm the intent with the user in one short summary: target outcomes, trigger contexts, output format, and key constraints.

### Step 2: Planning the Reusable Skill Contents

To turn concrete examples into an effective skill, analyze each example by:

1. Considering how to execute on the example from scratch
2. Identifying what scripts, references, and assets would be helpful when executing these workflows repeatedly

Example: When building a `pdf-editor` skill to handle queries like "Help me rotate this PDF," the analysis shows:

1. Rotating a PDF requires re-writing the same code each time
2. A `scripts/rotate_pdf.py` script would be helpful to store in the skill

Example: When designing a `frontend-webapp-builder` skill for queries like "Build me a todo app" or "Build me a dashboard to track my steps," the analysis shows:

1. Writing a frontend webapp requires the same boilerplate HTML/React each time
2. An `assets/hello-world/` template containing the boilerplate HTML/React project files would be helpful to store in the skill

Example: When building a `big-query` skill to handle queries like "How many users have logged in today?" the analysis shows:

1. Querying BigQuery requires re-discovering the table schemas and relationships each time
2. A `references/schema.md` file documenting the table schemas would be helpful to store in the skill

To establish the skill's contents, analyze each concrete example to create a list of the reusable resources to include: scripts, references, and assets.

### Step 3: Initializing the Skill

At this point, it is time to actually create the skill.

Skip this step only if the skill being developed already exists. In this case, continue to the next step.

When creating a new skill from scratch, always run the `init_skill.py` script. The script conveniently generates a new template skill directory that automatically includes everything a skill requires, making the skill creation process much more efficient and reliable.

Run these commands from repository root so `--path skills/public` resolves correctly.
These commands require `pyyaml`; run with `uv`.

Usage:

```bash
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/init_skill.py <skill-name> --path <output-directory> [--resources scripts,references,assets] [--examples]
```

Examples:

```bash
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/init_skill.py my-skill --path skills/public
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/init_skill.py my-skill --path skills/public --resources scripts,references
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/init_skill.py my-skill --path skills/public --resources scripts --examples
```

The script:

- Creates the skill directory at the specified path
- Generates a SKILL.md template with proper frontmatter and TODO placeholders
- Creates `agents/openai.yaml` using agent-generated `display_name`, `short_description`, and `default_prompt` passed via `--interface key=value`
- Optionally creates resource directories based on `--resources`
- Optionally adds example files when `--examples` is set

After initialization, customize the SKILL.md and add resources as needed. If you used `--examples`, replace or delete placeholder files.

Generate `display_name`, `short_description`, and `default_prompt` by reading the skill, then pass them as `--interface key=value` to `init_skill.py` or regenerate with:

```bash
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/generate_openai_yaml.py <path/to/skill-folder> --interface key=value
```

Only include other optional interface fields when the user explicitly provides them. For full field descriptions and examples, see references/openai_yaml.md.

### Step 4: Edit the Skill

When editing the (newly-generated or existing) skill, remember that the skill is being created for another instance of Codex to use. Include information that would be beneficial and non-obvious to Codex. Consider what procedural knowledge, domain-specific details, or reusable assets would help another Codex instance execute these tasks more effectively.

#### Start with Reusable Skill Contents

To begin implementation, start with the reusable resources identified above: `scripts/`, `references/`, and `assets/` files. Note that this step may require user input. For example, when implementing a `brand-guidelines` skill, the user may need to provide brand assets or templates to store in `assets/`, or documentation to store in `references/`.

Added scripts must be tested by actually running them to ensure there are no bugs and that the output matches what is expected. If there are many similar scripts, only a representative sample needs to be tested to ensure confidence that they all work while balancing time to completion.

If you used `--examples`, delete any placeholder files that are not needed for the skill. Only create resource directories that are actually required.

#### Update SKILL.md

**Writing Guidelines:** Always use imperative/infinitive form.

##### Frontmatter

Write the YAML frontmatter with `name` and `description`:

- `name`: The skill name
- `description`: This is the primary triggering mechanism for your skill, and helps Codex understand when to use the skill.
  - Include both what the Skill does and specific triggers/contexts for when to use it.
  - Include all "when to use" information here - Not in the body. The body is only loaded after triggering, so "When to Use This Skill" sections in the body are not helpful to Codex.
  - Example description for a `docx` skill: "Comprehensive document creation, editing, and analysis with support for tracked changes, comments, formatting preservation, and text extraction. Use when Codex needs to work with professional documents (.docx files) for: (1) Creating new documents, (2) Modifying or editing content, (3) Working with tracked changes, (4) Adding comments, or any other document tasks"

Do not include any other fields in YAML frontmatter.

##### Body

Write instructions for using the skill and its bundled resources.

### Step 5: Validate the Skill

Once development of the skill is complete, validate the skill folder to catch basic issues early:

Run this command from repository root.

```bash
uv run --with pyyaml python3 skills/.system/skill-creator/scripts/quick_validate.py <path/to/skill-folder>
```

The validation script checks YAML frontmatter format, required fields, and naming rules. If validation fails, fix the reported issues and run the command again.

### Step 6: Evaluate Test Cases with a Baseline

After validating structure and frontmatter, evaluate real behavior with realistic prompts. Do not rely on validation checks alone.

#### Choose Evaluation Mode

Choose evaluation mode based on task type.

1. Objective tasks: use assertions and baseline comparisons.
2. Subjective tasks: prioritize qualitative review and human feedback.
3. If baseline or quantitative checks are skipped, record the reason and define what evidence counts as success.

#### Build an Evaluation Set

Create 2-5 realistic prompts that mirror actual user requests. For each prompt, define expected outcomes in observable terms.

Recommended structure:

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": "invoice-cleanup-basic",
      "prompt": "User prompt text",
      "expected_output": "Observable result and quality bar",
      "files": []
    }
  ]
}
```

Use descriptive eval IDs and keep the set diverse enough to cover edge cases, not just the easiest happy path.

Keep one canonical eval manifest at `<skill-name>-workspace/evals.json` and reuse it for every iteration.
Store prompts and expected outcomes only in that manifest.
When intent stays the same, keep the same eval `id` across iterations.
Create a new eval `id` only when scope or acceptance criteria change.

#### Run Candidate and Baseline

For each eval, run two executions:

1. Candidate run using the current skill.
2. Baseline run:
   - New skill: run without the skill.
   - Existing skill update: run against a snapshot of the previous skill version.

When subagents are available, run candidate and baseline in parallel. Otherwise, run sequentially and keep inputs identical.

Store outputs by iteration and eval:

```
<skill-name>-workspace/
  iteration-1/
    <eval-id>/
      candidate/
      baseline/
```

Store only run artifacts in iteration folders.
Do not duplicate prompt text or expected outcomes inside `candidate/` or `baseline/`; reference eval `id` from the canonical manifest.

#### Grade and Review

While runs are executing, draft objective assertions for each eval where possible. Use qualitative review only for outputs that cannot be scored objectively.

For each run:

1. Record pass/fail results with short evidence.
2. Compare candidate vs baseline quality.
3. Record time/token signals if the environment exposes them.
4. Share side-by-side outputs with the user and collect feedback.

Tie every requested change to one or more eval IDs so later iterations remain traceable.

Maintain one comparison log (for example, `<skill-name>-workspace/results.md`) keyed by eval `id` and iteration.
Avoid duplicating the same evidence in multiple notes; link to artifact paths instead.

### Step 7: Improve the Skill from Evidence

Use evaluation results and user feedback to update SKILL.md and bundled resources.

#### Improvement Heuristics

1. Generalize from feedback. Avoid overfitting to a small fixed eval set.
2. Keep the prompt lean. Remove instructions that do not change outcomes.
3. Explain why constraints matter. Prefer rationale over rigid wording.
4. Promote repeated helper logic into scripts/ when multiple evals repeat the same work.

#### Improvement Loop

1. Apply targeted edits based on failing assertions or clear user feedback.
2. Re-run all evals into a new iteration directory.
3. Compare deltas against the prior iteration and baseline.
4. Repeat until one stop condition is met:
   - User confirms the skill is good enough.
   - Feedback is mostly empty and assertions are stable.
   - Additional iterations produce no meaningful improvements.

### Step 8: Optimize the Trigger Description (Optional)

After behavior is stable, optimize frontmatter description quality.

1. Draft a mixed trigger eval set (should-trigger and should-not-trigger queries).
2. Include near-miss negatives, not only obviously unrelated queries.
3. Revise description wording to improve trigger precision and recall.
4. Keep all trigger guidance in frontmatter; do not move trigger logic into body sections.
5. Reuse Step 6 eval IDs for trigger checks when possible; add trigger-specific IDs only for routing behavior not already covered.

### Step 9: Communicate Iteration Outcomes (Optional)

Report each iteration in a compact, consistent format:

1. Eval IDs that changed pass/fail status.
2. Candidate vs baseline deltas with one-line evidence.
3. Open risks and explicit user decisions needed.

Keep summaries brief and link to stored artifacts instead of duplicating content.

## Bundled Evaluation Tooling

Use bundled scripts when they reduce repeated manual work.

Prerequisites:

- Run all commands from the skill root: `skills/.system/skill-creator`.
- If running from repository root, prefix module commands with `PYTHONPATH=skills/.system/skill-creator`. For non-module scripts, use full paths (for example, `python3 skills/.system/skill-creator/eval-viewer/generate_review.py ...`).
- Use `uv` when a script requires third-party dependencies.
- Set `ANTHROPIC_API_KEY` before running description optimization scripts.

- `python3 -m scripts.run_eval --eval-set <eval-set.json> --skill-path <skill-path> > <eval-results.json>`
  - Evaluate trigger behavior against should-trigger and should-not-trigger prompts; this command prints JSON to stdout, so redirect it when you need an `--eval-results` file.
  - Add `--warn-timeouts` when you want per-query timeout diagnostics.
- `python3 -m scripts.aggregate_benchmark <benchmark-dir> --skill-name <name>`
  - Aggregate grading results into benchmark summaries from a directory containing `eval-*` subdirectories.
- `python3 eval-viewer/generate_review.py <workspace-dir> --skill-name "<name>"`
  - Generate a review UI for side-by-side output review (use the workspace root, or pass a single iteration directory to review only that iteration).
- `uv run --with anthropic python3 -m scripts.improve_description --eval-results <eval-results.json> --skill-path <skill-path> --model <model-id>`
  - Propose improved frontmatter descriptions from eval evidence.
- `uv run --with anthropic python3 -m scripts.run_loop --eval-set <eval-set.json> --skill-path <skill-path> --model <model-id>`
  - Run iterative trigger-eval and description-improvement cycles.
  - For very small eval sets (for example, fewer than 6 prompts), consider `--holdout 0` to avoid unstable train/test splits.
  - If the API returns a model-not-found error, retry with a currently available model ID (for example, `claude-sonnet-4-6`).
- `uv run --with pyyaml python3 -m scripts.package_skill <path/to/skill-folder> [output-directory]`
  - Build a distributable `.skill` archive after validation.

When you use these tools, read supporting docs as needed:

- `references/schemas.md` for eval, grading, and benchmark schemas.
- `agents/grader.md`, `agents/analyzer.md`, and `agents/comparator.md` for grading and analysis workflows.
- `assets/eval_review.html` as a template for manual trigger-eval set review.
