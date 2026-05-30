# Known Limitations

## MVP Scope

- Public GitHub PRs only.
- No GitHub write-back.
- No GitHub App installation.
- No persistent database.
- Session history is temporary.
- No full repository indexing.
- No test execution or compilation.

## AI Limitations

- May miss cross-file logic.
- May overestimate low-confidence risks.
- May produce incomplete analysis for truncated diffs.
- Requires human verification.
- Fallback result means the model output was not parseable or empty.

## Demo Risks

- GitHub API rate limit.
- LLM API outage or rate limit.
- Public PR may change.
- Full mode may take longer on large PRs.

## Recommended Mitigation

- Use Standard mode for live demo.
- Prepare backup screenshots.
- Prepare a short recorded demo.
- Use stable public PR examples.
