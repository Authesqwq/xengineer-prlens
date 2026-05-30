# Product Scope Evolution

## 1. Purpose

This document explains how PRLens evolved from the initial PRD to the final MVP.

The goal is to make the product process transparent. PRD v0.3 is a final scope-aligned document, not a claim that all implementation decisions were fixed before development.

## 2. PRD Versions

| Version | Role | Notes |
|---|---|---|
| v0.1 | Initial draft | Covered background, research, feature planning, technical direction, and PR breakdown. |
| v0.2 | AI product PRD | Added model selection, prompt engineering, evaluation plan, hallucination control, data loop, and launch strategy. |
| v0.3 | Final scope-aligned PRD | Updated after PR1-PR17 to reflect implemented MVP scope and deferred items. |

## 3. Why Scope Changed

The project was built under short-cycle training camp constraints. During implementation, the scope was adjusted based on:

- Development time
- Demo stability
- UX feedback
- API reliability
- LLM output robustness
- Need for a clear MVP boundary

## 4. Major Scope Adjustments

| Initial Plan | Final Decision | Reason |
|---|---|---|
| Example PR quick entry in the main page | Removed from main product flow | It created UI clutter and was less useful than documented demo cases |
| User feedback buttons for each risk | Deferred | Feedback loop requires persistence and is better suited for a deployed version |
| Generic result caching | Reframed as session-level history | Session history is sufficient for Demo and avoids database scope |
| Single full analysis flow | Replaced by Fast / Standard / Full modes | Allows users to control analysis depth |
| Static loading state | Replaced by step-by-step progress | Reduces user uncertainty during slow analysis |
| Basic result export | Implemented Markdown report export | Useful for demo and review handoff |
| Raw model error exposure | Replaced by structured fallback | Improves robustness and demo stability |

## 5. Final MVP Boundary

The final MVP focuses on:

- Public GitHub PR analysis
- Structured AI summary
- Risk analysis
- Review suggestion generation
- Analysis modes
- Session history
- Markdown export
- Bilingual UI
- Progress feedback
- Robust fallback

Out of scope:

- GitHub App
- GitHub write-back
- Private repository support
- Persistent database
- Team rule management
- Cloud user accounts
- Full repository indexing

## 6. Conclusion

PRLens followed an iterative MVP process. The final PRD v0.3 records the implemented product scope and explains which early ideas were completed, adjusted, or deferred.
