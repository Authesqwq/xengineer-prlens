"""
PRLens: AI PR Review Assistant — Streamlit Demo.

Ties together URL parsing, GitHub data fetching, diff processing,
LLM-based summary, risk analysis, and review suggestions into a single-page workflow.
"""

import os
import streamlit as st
from dotenv import load_dotenv

from src.pr_parser import PRUrlParseError, parse_github_pr_url
from src.github_client import (
    GitHubClientError,
    fetch_pr_files,
    fetch_pr_info,
)
from src.diff_processor import build_diff_context
from src.llm_client import (
    LLMClientError,
    LLMConfigError,
    load_llm_config_from_env,
)
from src.summary_analyzer import SummaryAnalyzerError, generate_pr_summary
from src.risk_analyzer import RiskAnalyzerError, analyze_pr_risks
from src.review_suggestion import (
    ReviewSuggestionError,
    generate_review_suggestions,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Display helpers (pure functions, testable)
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def format_pr_status(pr_info) -> str:
    """Return a human-readable PR status label."""
    state = pr_info.state.lower()
    merged = getattr(pr_info, "merged", False)
    if state == "open":
        return "Open"
    if state == "closed" and merged:
        return "Merged"
    if state == "closed":
        return "Closed"
    return pr_info.state.capitalize()


def _none_if_empty(items):
    """Return the list or None marker."""
    if not items:
        return ["None"]
    return items


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PRLens — AI PR Review Assistant", page_icon="🔍", layout="wide")
st.title("PRLens: AI PR Review Assistant")
st.markdown(
    "Enter a **public** GitHub Pull Request URL to generate an AI-powered "
    "change summary, risk analysis, and review suggestions."
)

# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------

EXAMPLE_PRS = [
    "",
    "https://github.com/octocat/Hello-World/pull/6",
    "https://github.com/fastapi/fastapi/pull/12000",
    "https://github.com/psf/requests/pull/6500",
]

selected_example = st.selectbox("Example PRs (or paste your own below)", EXAMPLE_PRS)

pr_url = st.text_input(
    "GitHub PR URL",
    value=selected_example,
    placeholder="https://github.com/owner/repo/pull/123",
)

col1, col2 = st.columns([1, 3])
with col1:
    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Sidebar — capability boundaries
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### About PRLens")
    st.markdown(
        "AI analysis is based on the PR title, description, changed files, "
        "and diff returned by the GitHub API. It may miss repository-level "
        "context, runtime behavior, hidden dependencies, and project-specific "
        "review rules."
    )
    st.info("This demo does **not** write comments back to GitHub.")

    st.markdown("### LLM Calls")
    st.markdown(
        "The demo may call the LLM up to three times: change summary, risk "
        "analysis, and review suggestions. If no risk items are found, review "
        "suggestion generation skips the third call."
    )

# ---------------------------------------------------------------------------
# Analyze handler
# ---------------------------------------------------------------------------

if analyze_clicked:
    if not pr_url.strip():
        st.warning("Please enter a GitHub PR URL.")
    else:
        summary_result = None
        risk_result = None
        review_suggestions_result = None

        try:
            with st.status("Analyzing PR...", expanded=True) as status:
                # Phase 1
                status.write("Parsing PR URL...")
                parsed = parse_github_pr_url(pr_url)

                # Phase 2
                status.write("Fetching PR info...")
                github_token = os.getenv("GITHUB_TOKEN") or None
                pr_info = fetch_pr_info(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

                # Phase 3
                status.write("Fetching changed files...")
                changed_files = fetch_pr_files(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

                # Phase 4
                status.write("Building diff context...")
                diff_context = build_diff_context(changed_files)

                # Shared config
                llm_config = load_llm_config_from_env()

                # Phase 5
                status.write("Generating change summary...")
                summary_result = generate_pr_summary(pr_info, diff_context, llm_config)

                # Phase 6
                status.write("Analyzing risks...")
                risk_result = analyze_pr_risks(pr_info, diff_context, llm_config)

                # Phase 7
                status.write("Generating review suggestions...")
                review_suggestions_result = generate_review_suggestions(
                    pr_info=pr_info,
                    diff_context=diff_context,
                    risk_result=risk_result,
                    llm_config=llm_config,
                )

                status.update(label="Analysis complete!", state="complete")

            # ================================================================
            # PR Overview
            # ================================================================
            st.subheader("PR Overview")
            st.markdown(f"**[{pr_info.title}]({pr_info.html_url})**")
            c_a, c_b, c_c, c_d, c_e = st.columns(5)
            c_a.metric("Status", format_pr_status(pr_info))
            c_b.metric("Author", pr_info.author)
            c_c.metric("Files Changed", pr_info.changed_files)
            c_d.metric("Additions", f"+{pr_info.additions}")
            c_e.metric("Deletions", f"-{pr_info.deletions}")
            st.caption(
                f"Created: {pr_info.created_at} | Commits: {pr_info.commits} | "
                f"State: {pr_info.state}"
            )
            if pr_info.body:
                with st.expander("PR Description"):
                    st.write(pr_info.body)

            # ================================================================
            # Changed Files
            # ================================================================
            if changed_files:
                st.subheader(f"Changed Files ({len(changed_files)})")
                file_data = []
                for f in changed_files[:50]:
                    file_data.append({
                        "File": f.filename,
                        "Status": f.status,
                        "+": f.additions,
                        "-": f.deletions,
                        "Δ": f.changes,
                        "Patch": "Yes" if f.patch else "No",
                    })
                st.dataframe(file_data, use_container_width=True, hide_index=True)
                if len(changed_files) > 50:
                    st.caption(f"... and {len(changed_files) - 50} more files")

            # ================================================================
            # Diff Context Stats
            # ================================================================
            st.subheader("Diff Context Stats")
            cols = st.columns(5)
            cols[0].metric("Total Files", diff_context.total_files)
            cols[1].metric("Included", diff_context.included_files)
            cols[2].metric("Skipped", diff_context.skipped_files)
            cols[3].metric("Truncated", diff_context.truncated_files)
            cols[4].metric("Chars", f"{diff_context.original_total_chars} → {diff_context.processed_total_chars}")
            if diff_context.was_truncated:
                st.warning("Diff context was truncated — analysis covers partial files only.")
            if diff_context.warnings:
                for w in diff_context.warnings:
                    st.info(w)
            else:
                st.caption("Warnings: None")

            # ================================================================
            # AI Change Summary
            # ================================================================
            if summary_result:
                st.subheader("AI Change Summary")
                st.markdown(summary_result.summary)

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**Main Changes**")
                    for item in _none_if_empty(summary_result.main_changes):
                        st.markdown(f"- {item}")
                with col_r:
                    st.markdown("**Affected Areas**")
                    for item in _none_if_empty(summary_result.affected_areas):
                        st.markdown(f"- {item}")

                st.markdown("**Uncertainties**")
                for item in _none_if_empty(summary_result.uncertainties):
                    st.markdown(f"- {item}")

            # ================================================================
            # Risk Analysis
            # ================================================================
            if risk_result:
                st.subheader("Risk Analysis")
                level = risk_result.overall_risk_level.capitalize()
                if risk_result.overall_risk_level == "high":
                    st.error(f"Overall Risk Level: **{level}**")
                elif risk_result.overall_risk_level == "medium":
                    st.warning(f"Overall Risk Level: **{level}**")
                else:
                    st.info(f"Overall Risk Level: **{level}**")

                if not risk_result.risk_items:
                    st.info(
                        "No obvious risks were found by the model. "
                        "Please still review the PR manually."
                    )
                else:
                    sorted_risks = sorted(
                        risk_result.risk_items,
                        key=lambda r: SEVERITY_ORDER.get(r.severity, 99),
                    )
                    for i, ri in enumerate(sorted_risks, 1):
                        sev_emoji = SEVERITY_EMOJI.get(ri.severity, "⚪")
                        with st.expander(
                            f"Risk {i}: {sev_emoji} [{ri.severity.upper()}] {ri.risk_type} — {ri.file_path}"
                        ):
                            st.markdown(f"**File:** `{ri.file_path or 'N/A'}`")
                            st.markdown(f"**Evidence:** {ri.evidence or 'N/A'}")
                            st.markdown(f"**Explanation:** {ri.explanation or 'N/A'}")
                            st.markdown(f"**Impact:** {ri.impact or 'N/A'}")
                            st.markdown(f"**Suggestion:** {ri.suggestion or 'N/A'}")
                            st.caption(
                                f"Confidence: {ri.confidence} | "
                                f"Need human check: {'Yes' if ri.need_human_check else 'No'}"
                            )

                st.markdown("**Limitations**")
                if risk_result.limitations:
                    for item in risk_result.limitations:
                        st.markdown(f"- {item}")
                else:
                    st.caption("None")

                st.info(
                    "Risk analysis is generated from PR diff only and may miss "
                    "repository-level context. Please verify before using it as review feedback."
                )

            # ================================================================
            # Review Suggestions
            # ================================================================
            if review_suggestions_result:
                st.subheader("Review Suggestions")

                if not review_suggestions_result.suggestions:
                    st.info(
                        "No review suggestions were generated because no concrete "
                        "risk items were found. Please still review the PR manually."
                    )
                else:
                    sorted_sugs = sorted(
                        review_suggestions_result.suggestions,
                        key=lambda s: PRIORITY_ORDER.get(s.priority, 99),
                    )
                    for i, sug in enumerate(sorted_sugs, 1):
                        prio_emoji = PRIORITY_EMOJI.get(sug.priority, "⚪")
                        with st.expander(
                            f"Suggestion {i}: {prio_emoji} [{sug.priority.upper()}] {sug.title}"
                        ):
                            st.markdown(f"**File:** `{sug.file_path or 'N/A'}`")
                            st.markdown(f"**Problem:** {sug.problem or 'N/A'}")
                            st.markdown(f"**Evidence:** {sug.evidence or 'N/A'}")
                            st.markdown(f"**Impact:** {sug.impact or 'N/A'}")
                            st.markdown(f"**Suggestion:** {sug.suggestion or 'N/A'}")
                            st.caption(
                                f"Source Risk Type: {sug.source_risk_type or 'N/A'} | "
                                f"Need human check: {'Yes' if sug.need_human_check else 'No'}"
                            )
                            st.markdown("**Copyable Review Comment:**")
                            st.code(sug.copy_text, language="markdown")

                st.markdown("**Limitations**")
                if review_suggestions_result.limitations:
                    for item in review_suggestions_result.limitations:
                        st.markdown(f"- {item}")
                else:
                    st.caption("None")

                st.info(
                    "Review suggestions are drafts generated from PR diff and risk "
                    "analysis. Please verify them before posting as code review comments."
                )

        except PRUrlParseError:
            st.error("Unable to parse PR URL. Please enter a valid GitHub PR URL, e.g. `https://github.com/owner/repo/pull/123`")
        except GitHubClientError as e:
            st.error(f"Failed to fetch PR data: {e}")
            st.info("Please check whether the PR exists, the repository is public, or your GitHub token is valid.")
        except LLMConfigError:
            st.error("Missing LLM configuration. Please set LLM_API_KEY, LLM_MODEL, and LLM_BASE_URL in `.env`.")
        except LLMClientError as e:
            st.error(f"LLM request failed: {e}")
            st.info("Please retry or check your model provider status.")
        except SummaryAnalyzerError as e:
            st.error(f"Summary generation failed: {e}")
        except RiskAnalyzerError as e:
            st.error(f"Risk analysis failed: {e}")
        except ReviewSuggestionError as e:
            st.error(f"Review suggestion generation failed: {e}")
        except ValueError as e:
            st.error(f"Input error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption("PRLens — AI PR Review Assistant | Local Demo")
