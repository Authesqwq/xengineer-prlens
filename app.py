"""
PRLens: AI PR Review Assistant — Minimal Streamlit Demo.

Ties together URL parsing, GitHub data fetching, diff processing,
and LLM-based summary generation into a single-page workflow.
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

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PRLens", page_icon="🔍", layout="wide")
st.title("PRLens: AI PR Review Assistant")
st.markdown(
    "Enter a **public** GitHub Pull Request URL to generate an AI-powered change summary."
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

            # ---------- Phase 5: Generate summary ----------
            with st.spinner("Generating AI summary..."):
                llm_config = load_llm_config_from_env()
                summary_result = generate_pr_summary(pr_info, diff_context, llm_config)

            # ====== Display results ======
            st.success("Analysis complete!")

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
                    for f in changed_files[:50]  # show first 50
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
        except ValueError as e:
            st.error(f"Input error: {e}")
        except Exception as e:
            st.error(f"Unexpected error: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption("PRLens — AI PR Review Assistant | Local Demo")
