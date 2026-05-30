# PRLens Evaluation Cases

## Purpose

This document records demo-oriented validation cases for PRLens.
It is not a formal academic benchmark. Its purpose is to make the demo flow reproducible and to clarify expected behavior.

## Case 1: octocat/Hello-World #6

- URL: https://github.com/octocat/Hello-World/pull/6
- Recommended Mode: Fast or Standard
- Why this case:
  - Small public PR.
  - Suitable for validating the basic end-to-end pipeline.
- Expected Behavior:
  - PR URL can be parsed.
  - PR metadata can be fetched.
  - Changed files can be displayed.
  - Summary can be generated.
- Demo Notes:
  - Use this case for a quick live demo.
- Known Risk:
  - The PR is very small, so it may not produce meaningful risks.

## Case 2: fastapi/fastapi #12000

- URL: https://github.com/fastapi/fastapi/pull/12000
- Recommended Mode: Standard
- Why this case:
  - Real-world public repository.
  - More suitable for showing diff context, risk analysis, and fallback handling.
- Expected Behavior:
  - PR metadata and changed files can be fetched.
  - Summary should explain the main change.
  - Risk analysis should either return structured risks or a graceful fallback.
- Demo Notes:
  - This case is useful for showing robustness.
- Known Risk:
  - Risk analysis may trigger fallback depending on model output.
  - This is acceptable because PRLens has fallback handling.

## Case 3: Custom Medium PR

- URL: To be verified
- Recommended Mode: Full
- Why this case:
  - Use a medium-sized PR to demonstrate Review Suggestions.
- Expected Behavior:
  - Summary, Risk Analysis, and Review Suggestions should all be generated.
- Demo Notes:
  - Fill this before final recording.

## Evaluation Checklist

- [ ] PR URL can be parsed.
- [ ] GitHub PR info can be fetched.
- [ ] Changed files can be displayed.
- [ ] Diff context stats are visible.
- [ ] Analysis progress updates.
- [ ] Elapsed time is shown.
- [ ] Summary is generated.
- [ ] Risk Analysis behaves correctly.
- [ ] Review Suggestions are generated in Full mode when risks exist.
- [ ] Export works.
- [ ] History restore works.
