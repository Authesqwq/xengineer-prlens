# PRLens Demo Script

## 1. 2-Minute Demo Script

### Opening

PR Review is time-consuming because reviewers need to understand intent, inspect diff, identify risks, and write actionable comments. PRLens helps reviewers quickly understand public GitHub PRs and generate structured review assistance.

### Demo Steps

1. Open PRLens.
2. Select language and Standard mode.
3. Paste a public GitHub PR URL.
4. Click Analyze PR.
5. Show step-by-step progress and elapsed time.
6. Show PR overview and changed files.
7. Show AI Change Summary.
8. Show Risk Analysis.
9. Show session history.
10. Export Markdown report.

### Closing

PRLens is a lightweight AI review assistant. It does not replace human review and does not write comments back to GitHub. It helps reviewers form a faster and more structured first pass.

## 2. 5-Minute Demo Script

### 1. Problem

PR Review requires reviewers to understand the purpose, inspect changed files, identify risks, and provide useful feedback. This process becomes harder when PR information is scattered and AI-generated code increases development speed.

### 2. Product Flow

PRLens uses a simple flow:

1. Paste a public GitHub PR URL.
2. Fetch PR metadata and changed files.
3. Build a diff context.
4. Generate AI summary, risk analysis, and review suggestions.
5. Display structured results and allow Markdown export.

### 3. Architecture

The system consists of:

- Streamlit UI
- PR URL Parser
- GitHub Client
- Diff Processor
- LLM Client
- Summary Analyzer
- Risk Analyzer
- Review Suggestion Generator
- Session History
- Markdown Export

### 4. Key Features

- Fast / Standard / Full modes
- Chinese / English UI
- Session-level history
- Markdown report export
- Progress feedback
- Elapsed time display
- Risk fallback for invalid or empty model output

### 5. Reliability

PRLens includes structured output parsing, fallback handling, error messages, diff truncation, and automated tests. The system is designed to avoid crashing when model output is empty or invalid.

### 6. Limitations

PRLens only analyzes public GitHub PRs. It does not access the full repository context, does not run tests, does not compile code, and does not write comments back to GitHub. Results require human verification.

### 7. Closing

PRLens is designed as a lightweight AI Review workspace for fast PR understanding, risk first-pass analysis, and review draft preparation.
