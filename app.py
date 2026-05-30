"""
PRLens: AI PR Review Assistant -- Streamlit Demo.

Bilingual (中文 / English) single-page workflow: URL parsing, GitHub data
fetching, diff processing, LLM summary, risk analysis, and review suggestions.
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
# Translations
# ---------------------------------------------------------------------------

T: dict[str, dict[str, str]] = {
    "zh": {
        "title": "PRLens: AI PR Review 助手",
        "subtitle": "输入一个公开 GitHub PR 链接，生成 AI 变更总结、风险分析和 Review 建议。",
        "lang_label": "语言 / Language",
        "pr_url_label": "GitHub PR 链接",
        "pr_url_placeholder": "https://github.com/octocat/Hello-World/pull/6",
        "examples_heading": "示例",
        "analyze_btn": "开始分析",
        "ph_parsing": "解析 PR 链接...",
        "ph_fetching_info": "获取 PR 基本信息...",
        "ph_fetching_files": "获取变更文件列表...",
        "ph_building_diff": "构建 diff 上下文...",
        "ph_summary": "生成变更总结...",
        "ph_risk": "分析风险...",
        "ph_suggestions": "生成 Review 建议...",
        "ph_done": "分析完成！",
        "pr_overview": "PR 概览",
        "status": "状态",
        "author": "作者",
        "changed_files_label": "变更文件",
        "additions": "新增行",
        "deletions": "删除行",
        "created": "创建时间",
        "commits": "提交数",
        "state_raw": "原始状态",
        "pr_description": "PR 描述",
        "changed_files_title": "变更文件列表",
        "file": "文件",
        "status_col": "状态",
        "plus": "新增",
        "minus": "删除",
        "delta": "变更",
        "patch_col": "Patch",
        "more_files": "... 还有 {n} 个文件",
        "diff_title": "Diff 上下文统计",
        "total_files": "文件总数",
        "included": "已纳入",
        "skipped": "已跳过",
        "truncated": "已截断",
        "chars": "字符数",
        "truncated_warning": "Diff 上下文已截断——本次分析仅覆盖部分文件。",
        "warnings_label": "警告",
        "warnings_empty": "无",
        "summary_title": "AI 变更总结",
        "main_changes": "主要变更",
        "affected_areas": "影响范围",
        "uncertainties": "不确定项",
        "none": "无",
        "risk_title": "风险分析",
        "risk_level": "总体风险等级",
        "risk_none_found": "模型未发现明显风险，但仍建议人工审查该 PR。",
        "risk_item_label": "风险项",
        "file_label": "文件",
        "evidence_label": "依据",
        "explanation_label": "解释",
        "impact_label": "影响",
        "suggestion_label": "建议",
        "confidence_label": "置信度",
        "need_human_label": "需人工确认",
        "limitations_label": "限制说明",
        "risk_disclaimer": "风险分析仅基于 PR diff 生成，可能遗漏仓库级上下文。请在使用前进行人工验证。",
        "sug_title": "Review 建议",
        "sug_none_found": "未生成 Review 建议，因为未发现具体风险项。请仍然人工审查该 PR。",
        "sug_item_label": "建议",
        "sug_problem": "问题",
        "sug_source_type": "来源风险类型",
        "sug_copy_label": "可复制 Review 评论",
        "sug_disclaimer": "Review 建议由 PR diff 和风险分析生成，仅为草稿。请在作为 Review 评论发布前进行人工验证。",
        "sidebar_about": "关于 PRLens",
        "sidebar_desc": "PRLens 基于 GitHub API 返回的 PR 标题、描述、变更文件和 diff 进行分析。可能遗漏仓库级上下文、运行时行为、隐藏依赖和项目特定的 Review 规则。",
        "sidebar_no_write": "本 Demo 不会向 GitHub 写入评论。",
        "sidebar_calls": "LLM 调用",
        "sidebar_calls_desc": "Demo 最多调用 LLM 三次：变更总结、风险分析和 Review 建议。如果未发现风险项，Review 建议将跳过第三次调用。",
        "err_parse": "无法解析 PR 链接。请输入有效的 GitHub PR URL，例如 `https://github.com/owner/repo/pull/123`",
        "err_github": "获取 PR 数据失败。请检查 PR 是否存在、仓库是否公开或 GitHub Token 是否有效。",
        "err_llm_config": "LLM 配置缺失。请在 `.env` 中设置 LLM_API_KEY、LLM_MODEL 和 LLM_BASE_URL。",
        "err_llm": "LLM 请求失败。请重试或检查模型供应商状态。",
        "err_summary": "变更总结生成失败。请重试或检查模型输出格式。",
        "err_risk": "风险分析失败。请重试或检查模型输出格式。",
        "err_suggestion": "Review 建议生成失败。请重试或检查模型输出格式。",
        "err_input": "输入错误。",
        "err_unexpected": "未知错误。",
        "footer": "PRLens — AI PR Review 助手 | 本地 Demo",
    },
    "en": {
        "title": "PRLens: AI PR Review Assistant",
        "subtitle": "Enter a public GitHub PR URL to generate an AI-powered change summary, risk analysis, and review suggestions.",
        "lang_label": "语言 / Language",
        "pr_url_label": "GitHub PR URL",
        "pr_url_placeholder": "https://github.com/octocat/Hello-World/pull/6",
        "examples_heading": "Examples",
        "analyze_btn": "Analyze",
        "ph_parsing": "Parsing PR URL...",
        "ph_fetching_info": "Fetching PR info...",
        "ph_fetching_files": "Fetching changed files...",
        "ph_building_diff": "Building diff context...",
        "ph_summary": "Generating change summary...",
        "ph_risk": "Analyzing risks...",
        "ph_suggestions": "Generating review suggestions...",
        "ph_done": "Analysis complete!",
        "pr_overview": "PR Overview",
        "status": "Status",
        "author": "Author",
        "changed_files_label": "Files Changed",
        "additions": "Additions",
        "deletions": "Deletions",
        "created": "Created",
        "commits": "Commits",
        "state_raw": "Raw state",
        "pr_description": "PR Description",
        "changed_files_title": "Changed Files",
        "file": "File",
        "status_col": "Status",
        "plus": "+",
        "minus": "-",
        "delta": "Δ",
        "patch_col": "Patch",
        "more_files": "... and {n} more files",
        "diff_title": "Diff Context Stats",
        "total_files": "Total Files",
        "included": "Included",
        "skipped": "Skipped",
        "truncated": "Truncated",
        "chars": "Chars",
        "truncated_warning": "Diff context was truncated -- analysis covers partial files only.",
        "warnings_label": "Warnings",
        "warnings_empty": "None",
        "summary_title": "AI Change Summary",
        "main_changes": "Main Changes",
        "affected_areas": "Affected Areas",
        "uncertainties": "Uncertainties",
        "none": "None",
        "risk_title": "Risk Analysis",
        "risk_level": "Overall Risk Level",
        "risk_none_found": "No obvious risks were found by the model. Please still review the PR manually.",
        "risk_item_label": "Risk",
        "file_label": "File",
        "evidence_label": "Evidence",
        "explanation_label": "Explanation",
        "impact_label": "Impact",
        "suggestion_label": "Suggestion",
        "confidence_label": "Confidence",
        "need_human_label": "Need human check",
        "limitations_label": "Limitations",
        "risk_disclaimer": "Risk analysis is generated from PR diff only and may miss repository-level context. Please verify before using it as review feedback.",
        "sug_title": "Review Suggestions",
        "sug_none_found": "No review suggestions were generated because no concrete risk items were found. Please still review the PR manually.",
        "sug_item_label": "Suggestion",
        "sug_problem": "Problem",
        "sug_source_type": "Source Risk Type",
        "sug_copy_label": "Copyable Review Comment",
        "sug_disclaimer": "Review suggestions are drafts generated from PR diff and risk analysis. Please verify them before posting as code review comments.",
        "sidebar_about": "About PRLens",
        "sidebar_desc": "PRLens analyzes PR title, description, changed files, and diff returned by the GitHub API. It may miss repository-level context, runtime behavior, hidden dependencies, and project-specific review rules.",
        "sidebar_no_write": "This demo does not write comments back to GitHub.",
        "sidebar_calls": "LLM Calls",
        "sidebar_calls_desc": "The demo may call the LLM up to three times: change summary, risk analysis, and review suggestions. If no risk items are found, review suggestion generation skips the third call.",
        "err_parse": "Unable to parse PR URL. Please enter a valid GitHub PR URL, e.g. `https://github.com/owner/repo/pull/123`",
        "err_github": "Failed to fetch PR data. Please check whether the PR exists, the repository is public, or your GitHub token is valid.",
        "err_llm_config": "Missing LLM configuration. Please set LLM_API_KEY, LLM_MODEL, and LLM_BASE_URL in `.env`.",
        "err_llm": "LLM request failed. Please retry or check your model provider status.",
        "err_summary": "Summary generation failed. Please retry or check model output format.",
        "err_risk": "Risk analysis failed. Please retry or check model output format.",
        "err_suggestion": "Review suggestion generation failed. Please retry or check model output format.",
        "err_input": "Input error.",
        "err_unexpected": "Unexpected error.",
        "footer": "PRLens -- AI PR Review Assistant | Local Demo",
    },
}


def t(lang: str, key: str, **fmt) -> str:
    text = T.get(lang, T["en"]).get(key, key)
    if fmt:
        text = text.format(**fmt)
    return text


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}

EXAMPLE_PRS = [
    "https://github.com/octocat/Hello-World/pull/6",
    "https://github.com/fastapi/fastapi/pull/12000",
    "https://github.com/psf/requests/pull/6500",
]


def format_pr_status(pr_info) -> str:
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
    return items if items else ["None"]


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PRLens", page_icon="🔍", layout="wide")

# -- Language picker in sidebar top --
with st.sidebar:
    lang = st.selectbox("语言 / Language", ["zh", "en"], format_func=lambda v: "中文" if v == "zh" else "English")
    st.divider()

# ---------------------------------------------------------------------------
# Title & intro
# ---------------------------------------------------------------------------

st.title(t(lang, "title"))
st.caption(t(lang, "subtitle"))

# ---------------------------------------------------------------------------
# Input area
# ---------------------------------------------------------------------------

# Preserve existing URL in session state when switching language
if "pr_url_value" not in st.session_state:
    st.session_state.pr_url_value = ""

pr_url = st.text_input(
    t(lang, "pr_url_label"),
    value=st.session_state.pr_url_value,
    placeholder=t(lang, "pr_url_placeholder"),
    key="pr_url_input",
)
st.session_state.pr_url_value = pr_url

# Lightweight example buttons
st.caption(t(lang, "examples_heading"))
cols = st.columns(len(EXAMPLE_PRS))
for i, example_url in enumerate(EXAMPLE_PRS):
    label = example_url.replace("https://github.com/", "")
    if cols[i].button(label, key=f"example_{i}", use_container_width=True):
        st.session_state.pr_url_value = example_url
        st.rerun()

analyze_clicked = st.button(t(lang, "analyze_btn"), type="primary")

# ---------------------------------------------------------------------------
# Sidebar -- capability info
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### {t(lang, 'sidebar_about')}")
    st.markdown(t(lang, "sidebar_desc"))
    st.info(t(lang, "sidebar_no_write"))
    st.markdown(f"### {t(lang, 'sidebar_calls')}")
    st.markdown(t(lang, "sidebar_calls_desc"))

# ---------------------------------------------------------------------------
# Analyze handler
# ---------------------------------------------------------------------------

if analyze_clicked:
    if not pr_url.strip():
        st.warning(t(lang, "err_parse"))
    else:
        summary_result = None
        risk_result = None
        review_suggestions_result = None

        try:
            with st.status(t(lang, "ph_parsing"), expanded=True) as status:
                status.write(t(lang, "ph_parsing"))
                parsed = parse_github_pr_url(pr_url)

                status.write(t(lang, "ph_fetching_info"))
                github_token = os.getenv("GITHUB_TOKEN") or None
                pr_info = fetch_pr_info(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

                status.write(t(lang, "ph_fetching_files"))
                changed_files = fetch_pr_files(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )

                status.write(t(lang, "ph_building_diff"))
                diff_context = build_diff_context(changed_files)

                llm_config = load_llm_config_from_env()

                status.write(t(lang, "ph_summary"))
                summary_result = generate_pr_summary(pr_info, diff_context, llm_config)

                status.write(t(lang, "ph_risk"))
                risk_result = analyze_pr_risks(pr_info, diff_context, llm_config)

                status.write(t(lang, "ph_suggestions"))
                review_suggestions_result = generate_review_suggestions(
                    pr_info=pr_info,
                    diff_context=diff_context,
                    risk_result=risk_result,
                    llm_config=llm_config,
                )

                status.update(label=t(lang, "ph_done"), state="complete")

            # ================================================================
            # PR Overview
            # ================================================================
            st.subheader(t(lang, "pr_overview"))
            st.markdown(f"**[{pr_info.title}]({pr_info.html_url})**")
            c_a, c_b, c_c, c_d, c_e = st.columns(5)
            c_a.metric(t(lang, "status"), format_pr_status(pr_info))
            c_b.metric(t(lang, "author"), pr_info.author)
            c_c.metric(t(lang, "changed_files_label"), pr_info.changed_files)
            c_d.metric(t(lang, "additions"), f"+{pr_info.additions}")
            c_e.metric(t(lang, "deletions"), f"-{pr_info.deletions}")
            st.caption(
                f"{t(lang, 'created')}: {pr_info.created_at} | "
                f"{t(lang, 'commits')}: {pr_info.commits} | "
                f"{t(lang, 'state_raw')}: {pr_info.state}"
            )
            if pr_info.body:
                with st.expander(t(lang, "pr_description")):
                    st.write(pr_info.body)

            # ================================================================
            # Changed Files
            # ================================================================
            if changed_files:
                st.subheader(t(lang, "changed_files_title") + f" ({len(changed_files)})")
                file_data = []
                for f in changed_files[:50]:
                    file_data.append({
                        t(lang, "file"): f.filename,
                        t(lang, "status_col"): f.status,
                        t(lang, "plus"): f.additions,
                        t(lang, "minus"): f.deletions,
                        t(lang, "delta"): f.changes,
                        t(lang, "patch_col"): "Yes" if f.patch else "No",
                    })
                st.dataframe(file_data, use_container_width=True, hide_index=True)
                if len(changed_files) > 50:
                    st.caption(t(lang, "more_files", n=len(changed_files) - 50))

            # ================================================================
            # Diff Context Stats
            # ================================================================
            st.subheader(t(lang, "diff_title"))
            dcols = st.columns(5)
            dcols[0].metric(t(lang, "total_files"), diff_context.total_files)
            dcols[1].metric(t(lang, "included"), diff_context.included_files)
            dcols[2].metric(t(lang, "skipped"), diff_context.skipped_files)
            dcols[3].metric(t(lang, "truncated"), diff_context.truncated_files)
            dcols[4].metric(
                t(lang, "chars"),
                f"{diff_context.original_total_chars} → {diff_context.processed_total_chars}",
            )
            if diff_context.was_truncated:
                st.warning(t(lang, "truncated_warning"))
            if diff_context.warnings:
                for w in diff_context.warnings:
                    st.info(w)
            else:
                st.caption(f"{t(lang, 'warnings_label')}: {t(lang, 'warnings_empty')}")

            # ================================================================
            # AI Change Summary
            # ================================================================
            if summary_result:
                st.subheader(t(lang, "summary_title"))
                st.markdown(summary_result.summary)

                col_l, col_r = st.columns(2)
                with col_l:
                    st.markdown(f"**{t(lang, 'main_changes')}**")
                    for item in _none_if_empty(summary_result.main_changes):
                        st.markdown(f"- {item}")
                with col_r:
                    st.markdown(f"**{t(lang, 'affected_areas')}**")
                    for item in _none_if_empty(summary_result.affected_areas):
                        st.markdown(f"- {item}")

                st.markdown(f"**{t(lang, 'uncertainties')}**")
                for item in _none_if_empty(summary_result.uncertainties):
                    st.markdown(f"- {item}")

            # ================================================================
            # Risk Analysis
            # ================================================================
            if risk_result:
                st.subheader(t(lang, "risk_title"))
                level = risk_result.overall_risk_level.capitalize()
                if risk_result.overall_risk_level == "high":
                    st.error(f"{t(lang, 'risk_level')}: **{level}**")
                elif risk_result.overall_risk_level == "medium":
                    st.warning(f"{t(lang, 'risk_level')}: **{level}**")
                else:
                    st.info(f"{t(lang, 'risk_level')}: **{level}**")

                if not risk_result.risk_items:
                    st.info(t(lang, "risk_none_found"))
                else:
                    sorted_risks = sorted(
                        risk_result.risk_items,
                        key=lambda r: SEVERITY_ORDER.get(r.severity, 99),
                    )
                    for i, ri in enumerate(sorted_risks, 1):
                        sev_emoji = SEVERITY_EMOJI.get(ri.severity, "⚪")
                        with st.expander(
                            f"{t(lang, 'risk_item_label')} {i}: {sev_emoji} [{ri.severity.upper()}] {ri.risk_type} -- {ri.file_path}"
                        ):
                            st.markdown(f"**{t(lang, 'file_label')}:** `{ri.file_path or 'N/A'}`")
                            st.markdown(f"**{t(lang, 'evidence_label')}:** {ri.evidence or 'N/A'}")
                            st.markdown(f"**{t(lang, 'explanation_label')}:** {ri.explanation or 'N/A'}")
                            st.markdown(f"**{t(lang, 'impact_label')}:** {ri.impact or 'N/A'}")
                            st.markdown(f"**{t(lang, 'suggestion_label')}:** {ri.suggestion or 'N/A'}")
                            st.caption(
                                f"{t(lang, 'confidence_label')}: {ri.confidence} | "
                                f"{t(lang, 'need_human_label')}: {'Yes' if ri.need_human_check else 'No'}"
                            )

                st.markdown(f"**{t(lang, 'limitations_label')}**")
                if risk_result.limitations:
                    for item in risk_result.limitations:
                        st.markdown(f"- {item}")
                else:
                    st.caption(t(lang, "none"))

                st.info(t(lang, "risk_disclaimer"))

            # ================================================================
            # Review Suggestions
            # ================================================================
            if review_suggestions_result:
                st.subheader(t(lang, "sug_title"))

                if not review_suggestions_result.suggestions:
                    st.info(t(lang, "sug_none_found"))
                else:
                    sorted_sugs = sorted(
                        review_suggestions_result.suggestions,
                        key=lambda s: PRIORITY_ORDER.get(s.priority, 99),
                    )
                    for i, sug in enumerate(sorted_sugs, 1):
                        prio_emoji = PRIORITY_EMOJI.get(sug.priority, "⚪")
                        with st.expander(
                            f"{t(lang, 'sug_item_label')} {i}: {prio_emoji} [{sug.priority.upper()}] {sug.title}"
                        ):
                            st.markdown(f"**{t(lang, 'file_label')}:** `{sug.file_path or 'N/A'}`")
                            st.markdown(f"**{t(lang, 'sug_problem')}:** {sug.problem or 'N/A'}")
                            st.markdown(f"**{t(lang, 'evidence_label')}:** {sug.evidence or 'N/A'}")
                            st.markdown(f"**{t(lang, 'impact_label')}:** {sug.impact or 'N/A'}")
                            st.markdown(f"**{t(lang, 'suggestion_label')}:** {sug.suggestion or 'N/A'}")
                            st.caption(
                                f"{t(lang, 'sug_source_type')}: {sug.source_risk_type or 'N/A'} | "
                                f"{t(lang, 'need_human_label')}: {'Yes' if sug.need_human_check else 'No'}"
                            )
                            st.markdown(f"**{t(lang, 'sug_copy_label')}:**")
                            st.code(sug.copy_text, language="markdown")

                st.markdown(f"**{t(lang, 'limitations_label')}**")
                if review_suggestions_result.limitations:
                    for item in review_suggestions_result.limitations:
                        st.markdown(f"- {item}")
                else:
                    st.caption(t(lang, "none"))

                st.info(t(lang, "sug_disclaimer"))

        except PRUrlParseError:
            st.error(t(lang, "err_parse"))
        except GitHubClientError as e:
            st.error(t(lang, "err_github") + f"\n\n({e})")
        except LLMConfigError:
            st.error(t(lang, "err_llm_config"))
        except LLMClientError as e:
            st.error(t(lang, "err_llm") + f"\n\n({e})")
        except SummaryAnalyzerError as e:
            st.error(t(lang, "err_summary") + f"\n\n({e})")
        except RiskAnalyzerError as e:
            st.error(t(lang, "err_risk") + f"\n\n({e})")
        except ReviewSuggestionError as e:
            st.error(t(lang, "err_suggestion") + f"\n\n({e})")
        except ValueError as e:
            st.error(t(lang, "err_input") + f"\n\n({e})")
        except Exception as e:
            st.error(t(lang, "err_unexpected") + f"\n\n({e})")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(t(lang, "footer"))
