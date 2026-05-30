# PRLens: AI PR Review Assistant

## Overview

PRLens is a lightweight AI PR Review Assistant for public GitHub Pull Requests.

Paste a GitHub PR URL and PRLens fetches PR metadata, changed files, and diff context, then generates:

- **AI Change Summary** — understand what changed and why
- **Risk Analysis** — identify potential logic, boundary, security, and performance issues
- **Review Suggestions** — structured, copyable review comment drafts
- **Markdown Report** — export results for sharing or documentation

PRLens helps reviewers form a faster first pass. It does **not** replace human review and does **not** write comments back to GitHub.

## Why PRLens

- PR information is scattered across title, description, files, diff, and comments
- Reviewers need time to understand intent and impact before giving useful feedback
- Risk identification is inconsistent across reviewers
- AI code generation increases PR volume and review pressure
- Existing commercial tools are powerful but often require deeper team-level integration

PRLens fills the gap for lightweight, low-setup PR inspection — no installation, no permissions, just a URL.

## Key Features

- GitHub PR URL parsing
- PR metadata fetching (title, author, state, stats)
- Changed files and patch fetching (paginated)
- Diff context building (file sorting, per-file and total truncation)
- **AI Change Summary** (LLM-generated structured summary)
- **Risk Analysis** (8 risk types: logic, boundary, error handling, testing, security, performance, compatibility, maintainability)
- **Review Suggestions** (copyable review comment drafts with evidence)
- **Fast / Standard / Full** analysis modes
- **Chinese / English** bilingual UI and model output
- Session-level **history** (up to 10 items, click to restore)
- **Markdown report export** (`st.download_button`)
- Step-by-step **progress feedback** with elapsed time
- Risk **fallback** for empty or invalid model output (graceful degradation, no crashes)

## Product Scope Evolution

PRD v0.2 was used as the initial product planning document. During PR1-PR17, the product scope was adjusted based on implementation constraints, demo stability, and UX feedback.

PRD v0.3 is the **final scope-aligned PRD** for delivery. It documents the implemented MVP scope and deferred items — it is not a claim that all decisions were fixed before development.

Key scope adjustments: example PR UI was removed, user feedback buttons were deferred, session history replaced result caching, analysis modes replaced a single flow, and fallback handling was added for robustness.

See [docs/product_evolution.md](docs/product_evolution.md) for details.

## Demo Flow

1. Select language and Standard mode in the sidebar
2. Paste a public GitHub PR URL
3. Click **Analyze PR**
4. Watch step-by-step progress
5. Review PR overview and changed files
6. Check diff context statistics
7. Read AI Change Summary
8. Review Risk Analysis
9. Switch to Full mode to generate Review Suggestions
10. Restore previous results from history
11. Export Markdown report

## Analysis Modes

| Mode | Runs | Does Not Run | Best For |
|---|---|---|---|
| Fast | Change Summary | Risk Analysis, Review Suggestions | Quickly understanding what changed |
| Standard | Change Summary, Risk Analysis | Review Suggestions | Normal pre-review check |
| Full | Change Summary, Risk Analysis, Review Suggestions | — | Preparing review comment drafts |

## Architecture

```
Streamlit UI
  ├── PR URL Parser (pr_parser.py)
  ├── GitHub Client (github_client.py)
  │     ├── PR Info
  │     └── Changed Files + Patch
  ├── Diff Processor (diff_processor.py)
  ├── LLM Client (llm_client.py)
  ├── Summary Analyzer (summary_analyzer.py)
  ├── Risk Analyzer (risk_analyzer.py)
  └── Review Suggestion Generator (review_suggestion.py)
        └── Results → Session History → Markdown Export
```

## Project Structure

```
.
├── app.py                          # Streamlit application
├── src/
│   ├── pr_parser.py                # GitHub PR URL parser
│   ├── github_client.py            # GitHub REST API client
│   ├── diff_processor.py           # Diff cleaning and context builder
│   ├── llm_client.py               # OpenAI-compatible LLM client
│   ├── summary_analyzer.py         # AI change summary generator
│   ├── risk_analyzer.py            # Risk identification module
│   └── review_suggestion.py        # Review suggestion generator
├── tests/                          # Pytest test suite (266 tests)
├── docs/                           # Product and delivery documents
├── prompts/                        # Prompt design specifications
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS / Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL=your-model-name
GITHUB_TOKEN=optional_github_token
```

- `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` are **required**.
- `GITHUB_TOKEN` is optional for public repos but recommended to reduce rate-limit risk.
- `.env` must **not** be committed.

## Run Demo

```bash
streamlit run app.py
```

## Run Tests

```bash
pytest -q
```

Result: **266 passed, 0 failed** (as of PR18).

## Demo Cases

- https://github.com/octocat/Hello-World/pull/6 — small PR, suitable for quick demo
- https://github.com/fastapi/fastapi/pull/12000 — shows risk analysis and fallback handling

See [docs/evaluation_cases.md](docs/evaluation_cases.md) for detailed case descriptions.

## Documents

| Document | Description |
|---|---|
| [docs/prd.md](docs/prd.md) | Final scope-aligned PRD (v0.3) |
| [docs/prlens_prd_v0.3.md](docs/prlens_prd_v0.3.md) | Archived PRD v0.3 |
| [docs/product_evolution.md](docs/product_evolution.md) | PRD and scope evolution |
| [docs/evaluation_cases.md](docs/evaluation_cases.md) | Demo evaluation cases |
| [docs/demo_script.md](docs/demo_script.md) | 2-minute and 5-minute demo scripts |
| [docs/final_submission.md](docs/final_submission.md) | Final submission checklist |
| [docs/known_limitations.md](docs/known_limitations.md) | Known limitations and risks |
| [docs/prlens_product_audit.md](docs/prlens_product_audit.md) | Product audit report |
| [docs/evaluation.md](docs/evaluation.md) | Evaluation framework |
| [prompts/summary_prompt.md](prompts/summary_prompt.md) | Summary prompt design |
| [prompts/review_prompt.md](prompts/review_prompt.md) | Review prompt design |
| [prompts/output_schema.md](prompts/output_schema.md) | Model output schema |

## Known Limitations

- Public GitHub PRs only in MVP
- Does not write comments back to GitHub
- Analysis is based on PR title, description, changed files, and diff only
- May miss repository-level context and cross-file logic
- Does not run tests or compile code
- Long diffs may be truncated
- LLM output requires human verification
- Session history is not persistent across browser restarts

## Product Positioning

PRLens is a lightweight AI review workspace for public GitHub PRs. It is **not** a replacement for enterprise platforms like GitHub Copilot Code Review, CodeRabbit, or Qodo. It fills the gap for quick, low-setup PR understanding and structured review draft preparation.

## Development Process

- **PR1-PR6**: Project foundation, GitHub/diff pipeline, LLM client
- **PR7-PR13**: Summary, risk analysis, review suggestions, Streamlit demo
- **PR14-PR17**: UX polish, fallback, workspace sidebar, history, modes, progress
- **PR18**: Final documentation and demo preparation
