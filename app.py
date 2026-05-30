"""
PRLens: AI PR Review Assistant — Minimal Streamlit Demo.

Ties together URL parsing, GitHub data fetching, diff processing,
LLM-based summary generation, and risk analysis into a single-page workflow.
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
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PRLens", page_icon="🔍", layout="wide")
st.title("PRLens: AI PR Review Assistant")
st.markdown(
    "Enter a **public** GitHub Pull Request URL to generate an AI-powered "
    "change summary and risk analysis."
)

# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------

pr_url = st.text_input(
    "GitHub PR URL",
    placeholder="https://github.com/owner/repo/pull/123",
)

col1, col2 = st.columns([1, 3])
with col1:
    analyze_clicked = st.button("Analyze", type="primary", use_container_width=True)

st.caption(
    "Try a public GitHub PR URL, for example: "
    "`https://github.com/psf/requests/pull/6500`"
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
            # ---------- Phase 1: Parse URL ----------
            with st.spinner("Parsing PR URL..."):
                parsed = parse_github_pr_url(pr_url)

            # ---------- Phase 2: Fetch PR info ----------
            github_token = os.getenv("GITHUB_TOKEN") or None

            with st.spinner("Fetching PR info..."):
                pr_info = fetch_pr_info(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

            # ---------- Phase 3: Fetch changed files ----------
            with st.spinner("Fetching changed files..."):
                changed_files = fetch_pr_files(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

            # ---------- Phase 4: Build diff context ----------
            with st.spinner("Building diff context..."):
                diff_context = build_diff_context(changed_files)

            # ---------- Shared LLM config ----------
            llm_config = load_llm_config_from_env()

            # ---------- Phase 5: Generate summary ----------
            with st.spinner("Generating change summary..."):
                summary_result = generate_pr_summary(pr_info, diff_context, llm_config)

            # ---------- Phase 6: Analyze risks ----------
            with st.spinner("Analyzing risks..."):
                risk_result = analyze_pr_risks(pr_info, diff_context, llm_config)

            # ---------- Phase 7: Generate review suggestions ----------
            with st.spinner("Generating review suggestions..."):
                review_suggestions_result = generate_review_suggestions(
                    pr_info=pr_info,
                    diff_context=diff_context,
                    risk_result=risk_result,
                    llm_config=llm_config,
                )

            st.success("Analysis complete!")

            # ====== Display results ======

            # -- PR Info --
            st.subheader("PR Overview")
            st.markdown(f"**[{pr_info.title}]({pr_info.html_url})**")
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Author", pr_info.author)
            col_b.metric("State", pr_info.state.capitalize())
            col_c.metric("Files Changed", pr_info.changed_files)
            col_d.metric("Commits", pr_info.commits)
            st.caption(
                f"Created: {pr_info.created_at} | "
                f"Additions: +{pr_info.additions} | "
                f"Deletions: -{pr_info.deletions} | "
                f"Merged: {'Yes' if pr_info.merged else 'No'}"
            )
            if pr_info.body:
                with st.expander("PR Description"):
                    st.write(pr_info.body)

            # -- Changed files --
            if changed_files:
                st.subheader(f"Changed Files ({len(changed_files)})")
                file_data = [
                    {
                        "File": f.filename,
                        "Status": f.status,
                        "+": f.additions,
                        "-": f.deletions,
                        "Changes": f.changes,
                        "Has Patch": "Yes" if f.patch else "No",
                    }
                    for f in changed_files[:50]
                ]
                st.dataframe(file_data, use_container_width=True, hide_index=True)
                if len(changed_files) > 50:
                    st.caption(f"... and {len(changed_files) - 50} more files")

            # -- Diff context stats --
            st.subheader("Diff Context Stats")
            cols = st.columns(4)
            cols[0].metric("Total Files", diff_context.total_files)
            cols[1].metric("Included", diff_context.included_files)
            cols[2].metric("Skipped", diff_context.skipped_files)
            cols[3].metric("Truncated", diff_context.truncated_files)
            if diff_context.was_truncated:
                st.warning("Diff context was truncated — analysis covers partial files only.")
            for w in diff_context.warnings:
                st.info(w)

            # -- AI Summary --
            if summary_result:
                st.subheader("AI Change Summary")
                st.markdown(summary_result.summary)

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown("**Main Changes**")
                    if summary_result.main_changes:
                        for item in summary_result.main_changes:
                            st.markdown(f"- {item}")
                    else:
                        st.caption("None")
                with col_r:
                    st.markdown("**Affected Areas**")
                    if summary_result.affected_areas:
                        for item in summary_result.affected_areas:
                            st.markdown(f"- {item}")
                    else:
                        st.caption("None")

                st.markdown("**Uncertainties**")
                if summary_result.uncertainties:
                    for item in summary_result.uncertainties:
                        st.markdown(f"- {item}")
                else:
                    st.caption("None")

            # ====== Risk Analysis ======
            if risk_result:
                st.subheader("Risk Analysis")

                # Overall level
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
                    severity_order = {"high": 0, "medium": 1, "low": 2}
                    sorted_items = sorted(
                        risk_result.risk_items,
                        key=lambda r: severity_order.get(r.severity, 99),
                    )

                    for i, ri in enumerate(sorted_items, 1):
                        sev_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(ri.severity, "⚪")
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

                # Limitations
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

            # ====== Review Suggestions ======
            if review_suggestions_result:
                st.subheader("Review Suggestions")

                if not review_suggestions_result.suggestions:
                    st.info(
                        "No review suggestions were generated because no concrete "
                        "risk items were found. Please still review the PR manually."
                    )
                else:
                    priority_order = {"high": 0, "medium": 1, "low": 2}
                    sorted_suggestions = sorted(
                        review_suggestions_result.suggestions,
                        key=lambda s: priority_order.get(s.priority, 99),
                    )

                    for i, sug in enumerate(sorted_suggestions, 1):
                        prio_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sug.priority, "⚪")
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

                # Limitations
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

        except PRUrlParseError as e:
            st.error(f"Unable to parse PR URL: {e}")
            st.info("Please enter a valid GitHub Pull Request URL, e.g. `https://github.com/owner/repo/pull/123`")
        except GitHubClientError as e:
            st.error(f"GitHub API error: {e}")
            st.info("Check that the PR exists, the repository is public, or your GitHub token is valid.")
        except LLMConfigError as e:
            st.error(f"LLM configuration error: {e}")
            st.info("Please set LLM_API_KEY, LLM_MODEL, and LLM_BASE_URL in your .env file.")
        except LLMClientError as e:
            st.error(f"LLM API error: {e}")
        except SummaryAnalyzerError as e:
            st.error(f"Summary generation error: {e}")
        except RiskAnalyzerError as e:
            st.error(f"Risk analysis error: {e}")
        except ReviewSuggestionError as e:
            st.error(f"Review suggestion error: {e}")
        except ValueError as e:
            st.error(f"Input error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption("PRLens — AI PR Review Assistant | Local Demo")
