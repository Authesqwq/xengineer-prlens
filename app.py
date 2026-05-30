"""
PRLens: AI PR Review Assistant -- Streamlit Demo.

Bilingual (中文 / English) single-page workflow: URL parsing, GitHub data fetching,
diff processing, LLM summary, risk analysis, and review suggestions.
"""

import os
import io
import json
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
# CSS — hide Streamlit chrome, keep product styling
# ---------------------------------------------------------------------------

CSS = """
<style>
#MainMenu { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }
footer { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
button[title="View fullscreen"] { display: none !important; }

.block-container { max-width: 1100px; padding-top: 1.5rem; padding-bottom: 3rem; }

.prlens-hero { padding: 0.5rem 0 0.5rem 0; }
.prlens-hero h1 { font-size: 2rem; font-weight: 700; margin: 0; }

.prlens-card {
    background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px;
    padding: 20px 22px; margin: 14px 0;
    box-shadow: 0 6px 18px rgba(15,23,42,0.04);
}

.prlens-muted { color: #64748b; font-size: 0.9rem; }

.prlens-badge {
    display: inline-block; padding: 4px 10px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600;
}
.prlens-badge-high { background: #fef2f2; color: #dc2626; }
.prlens-badge-medium { background: #fffbeb; color: #d97706; }
.prlens-badge-low { background: #f0fdf4; color: #16a34a; }

.prlens-lang-row { margin: 0.5rem 0 1rem 0; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

T: dict[str, dict[str, str]] = {
    "zh": {
        "title": "PRLens: AI PR Review 助手",
        "subtitle": "输入 GitHub Pull Request 链接，快速生成变更总结、风险分析和 Review 建议。",
        "lang_label": "界面语言",
        "pr_url_label": "GitHub PR 链接",
        "pr_url_placeholder": "请输入公开 GitHub PR 链接，例如：https://github.com/owner/repo/pull/123",
        "analyze_btn": "开始分析",
        "export_btn": "导出分析报告",
        "export_filename": "prlens_report.md",
        "export_heading": "# PRLens 分析报告",
        "export_overview": "## PR 概览",
        "export_title_row": "- 标题: {title}",
        "export_status_row": "- 状态: {status}",
        "export_author_row": "- 作者: {author}",
        "export_files_row": "- 变更文件: {files}",
        "export_additions_row": "- 新增行: +{additions}",
        "export_deletions_row": "- 删除行: -{deletions}",
        "export_commits_row": "- 提交数: {commits}",
        "export_summary_title": "## AI 变更总结",
        "export_summary": "### 变更总结",
        "export_main_changes": "### 主要变更",
        "export_affected_areas": "### 影响范围",
        "export_uncertainties": "### 不确定项",
        "export_risk_title": "## 风险分析",
        "export_risk_level": "### 总体风险等级: {level}",
        "export_risk_none": "模型未发现明显风险。",
        "export_risk_items": "### 风险项",
        "export_risk_limitations": "### 限制说明",
        "export_sug_title": "## Review 建议",
        "export_sug_none": "未生成 Review 建议。",
        "export_footer": "---\n*由 PRLens 生成 | 分析仅基于 PR diff*",
        "ph_parsing": "解析链接",
        "ph_fetching_info": "获取 PR 信息",
        "ph_fetching_files": "获取变更文件",
        "ph_building_diff": "构建上下文",
        "ph_summary": "生成总结",
        "ph_risk": "分析风险",
        "ph_suggestions": "生成建议",
        "ph_done": "分析完成",
        "pr_overview": "PR 概览",
        "status": "状态",
        "author": "作者",
        "changed_files_label": "变更文件",
        "additions": "新增行",
        "deletions": "删除行",
        "commits": "提交数",
        "state_open": "打开",
        "state_merged": "已合并",
        "state_closed": "已关闭",
        "pr_description": "PR 描述",
        "changed_files_title": "变更文件列表",
        "file": "文件",
        "status_col": "状态",
        "plus": "+",
        "minus": "-",
        "delta": "变更",
        "patch_col": "Patch",
        "patch_yes": "有",
        "patch_no": "无",
        "more_files": "... 还有 {n} 个文件",
        "diff_title": "Diff 上下文统计",
        "total_files": "文件总数",
        "included": "已纳入",
        "skipped": "已跳过",
        "truncated": "已截断",
        "chars": "字符数",
        "truncated_warning": "Diff 上下文已截断——本次分析仅覆盖部分文件。",
        "warnings_empty": "无",
        "summary_title": "AI 变更总结",
        "main_changes": "主要变更",
        "affected_areas": "影响范围",
        "uncertainties": "不确定项",
        "none": "无",
        "na": "不适用",
        "risk_title": "风险分析",
        "risk_level": "总体风险等级",
        "risk_low": "低风险",
        "risk_medium": "中风险",
        "risk_high": "高风险",
        "risk_none_found": "模型未发现明显风险，但仍建议人工审查该 PR。",
        "risk_item_label": "风险项",
        "file_label": "文件",
        "evidence_label": "依据",
        "explanation_label": "解释",
        "impact_label": "影响",
        "suggestion_label": "建议",
        "confidence_label": "置信度",
        "need_human_label": "需人工确认",
        "yes": "是",
        "no": "否",
        "limitations_label": "限制说明",
        "risk_disclaimer": "风险分析仅基于 PR diff 生成，可能遗漏仓库级上下文。请在使用前进行人工验证。",
        "sug_title": "Review 建议",
        "sug_none_found": "未生成 Review 建议，因为未发现具体风险项。请仍然人工审查该 PR。",
        "sug_item_label": "建议",
        "sug_problem": "问题",
        "sug_source_type": "来源风险类型",
        "sug_copy_label": "可复制 Review 评论",
        "sug_disclaimer": "Review 建议由 PR diff 和风险分析生成仅为草稿。请在使用前进行人工验证。",
        "err_parse": "请输入有效的 GitHub Pull Request 链接。",
        "err_github": "获取 PR 数据失败，请检查 PR 是否存在、仓库是否公开或 Token 是否有效。",
        "err_llm_config": "缺少 LLM 配置，请在 .env 中设置 LLM_API_KEY、LLM_MODEL 和 LLM_BASE_URL。",
        "err_llm": "LLM 请求失败，请重试或检查模型供应商状态。",
        "err_summary": "变更总结生成失败，已保留其他分析结果。",
        "err_risk": "风险分析暂时失败，已保留其他分析结果。",
        "err_suggestion": "Review 建议生成失败，已保留其他分析结果。",
        "err_input": "输入错误。",
        "err_unexpected": "未知错误，请重试。",
        "footer": "分析仅基于 GitHub API 返回的 PR 标题、描述、变更文件和 diff。结果可能遗漏仓库级上下文、运行时行为、隐藏依赖和项目特定 Review 规则。请在使用前进行人工验证。",
        "footer_about": "PRLens — AI PR Review 助手",
    },
    "en": {
        "title": "PRLens: AI PR Review Assistant",
        "subtitle": "Paste a GitHub Pull Request URL to generate a change summary, risk analysis, and review suggestions.",
        "lang_label": "Language",
        "pr_url_label": "GitHub PR URL",
        "pr_url_placeholder": "Enter a public GitHub PR URL, e.g. https://github.com/owner/repo/pull/123",
        "analyze_btn": "Analyze PR",
        "export_btn": "Download Report",
        "export_filename": "prlens_report.md",
        "export_heading": "# PRLens Analysis Report",
        "export_overview": "## PR Overview",
        "export_title_row": "- Title: {title}",
        "export_status_row": "- Status: {status}",
        "export_author_row": "- Author: {author}",
        "export_files_row": "- Changed Files: {files}",
        "export_additions_row": "- Additions: +{additions}",
        "export_deletions_row": "- Deletions: -{deletions}",
        "export_commits_row": "- Commits: {commits}",
        "export_summary_title": "## AI Change Summary",
        "export_summary": "### Summary",
        "export_main_changes": "### Main Changes",
        "export_affected_areas": "### Affected Areas",
        "export_uncertainties": "### Uncertainties",
        "export_risk_title": "## Risk Analysis",
        "export_risk_level": "### Overall Risk Level: {level}",
        "export_risk_none": "No obvious risks were found by the model.",
        "export_risk_items": "### Risk Items",
        "export_risk_limitations": "### Limitations",
        "export_sug_title": "## Review Suggestions",
        "export_sug_none": "No review suggestions were generated.",
        "export_footer": "---\n*Generated by PRLens | Analysis based on PR diff only*",
        "ph_parsing": "Parse URL",
        "ph_fetching_info": "Fetch PR info",
        "ph_fetching_files": "Fetch changed files",
        "ph_building_diff": "Build context",
        "ph_summary": "Generate summary",
        "ph_risk": "Analyze risks",
        "ph_suggestions": "Generate suggestions",
        "ph_done": "Analysis complete",
        "pr_overview": "PR Overview",
        "status": "Status",
        "author": "Author",
        "changed_files_label": "Files Changed",
        "additions": "Additions",
        "deletions": "Deletions",
        "commits": "Commits",
        "state_open": "Open",
        "state_merged": "Merged",
        "state_closed": "Closed",
        "pr_description": "PR Description",
        "changed_files_title": "Changed Files",
        "file": "File",
        "status_col": "Status",
        "plus": "+",
        "minus": "-",
        "delta": "Changes",
        "patch_col": "Patch",
        "patch_yes": "Yes",
        "patch_no": "No",
        "more_files": "... and {n} more files",
        "diff_title": "Diff Context Stats",
        "total_files": "Total Files",
        "included": "Included",
        "skipped": "Skipped",
        "truncated": "Truncated",
        "chars": "Chars",
        "truncated_warning": "Diff context was truncated -- analysis covers partial files only.",
        "warnings_empty": "None",
        "summary_title": "AI Change Summary",
        "main_changes": "Main Changes",
        "affected_areas": "Affected Areas",
        "uncertainties": "Uncertainties",
        "none": "None",
        "na": "N/A",
        "risk_title": "Risk Analysis",
        "risk_level": "Overall Risk Level",
        "risk_low": "Low",
        "risk_medium": "Medium",
        "risk_high": "High",
        "risk_none_found": "No obvious risks were found by the model. Please still review the PR manually.",
        "risk_item_label": "Risk",
        "file_label": "File",
        "evidence_label": "Evidence",
        "explanation_label": "Explanation",
        "impact_label": "Impact",
        "suggestion_label": "Suggestion",
        "confidence_label": "Confidence",
        "need_human_label": "Need human check",
        "yes": "Yes",
        "no": "No",
        "limitations_label": "Limitations",
        "risk_disclaimer": "Risk analysis is generated from PR diff only and may miss repository-level context. Please verify before using it as review feedback.",
        "sug_title": "Review Suggestions",
        "sug_none_found": "No review suggestions were generated because no concrete risk items were found. Please still review the PR manually.",
        "sug_item_label": "Suggestion",
        "sug_problem": "Problem",
        "sug_source_type": "Source Risk Type",
        "sug_copy_label": "Copyable Review Comment",
        "sug_disclaimer": "Review suggestions are drafts generated from PR diff and risk analysis. Please verify them before posting as code review comments.",
        "err_parse": "Please enter a valid GitHub Pull Request URL.",
        "err_github": "Failed to fetch PR data. Please check whether the PR exists, the repository is public, or the token is valid.",
        "err_llm_config": "Missing LLM configuration. Please set LLM_API_KEY, LLM_MODEL, and LLM_BASE_URL in .env.",
        "err_llm": "LLM request failed. Please retry or check your model provider status.",
        "err_summary": "Summary generation failed. Other analysis results are preserved.",
        "err_risk": "Risk analysis failed temporarily. Other analysis results are preserved.",
        "err_suggestion": "Review suggestion generation failed. Other analysis results are preserved.",
        "err_input": "Input error.",
        "err_unexpected": "Unexpected error. Please try again.",
        "footer": "The analysis is based on PR title, description, changed files, and diff returned by GitHub API. It may miss repository-level context, runtime behavior, hidden dependencies, and project-specific review rules. Please verify before use.",
        "footer_about": "PRLens -- AI PR Review Assistant",
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
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def format_pr_status(pr_info, lang: str) -> str:
    state = pr_info.state.lower()
    merged = getattr(pr_info, "merged", False)
    if state == "open":
        return t(lang, "state_open")
    if state == "closed" and merged:
        return t(lang, "state_merged")
    if state == "closed":
        return t(lang, "state_closed")
    return pr_info.state.capitalize()


def _none_if_empty(items, lang: str):
    if not items:
        return [t(lang, "none")]
    return items


def _risk_level_badge_class(level: str) -> str:
    m = {"high": "prlens-badge prlens-badge-high",
         "medium": "prlens-badge prlens-badge-medium"}
    return m.get(level, "prlens-badge prlens-badge-low")


def _risk_level_label(level: str, lang: str) -> str:
    m = {"high": t(lang, "risk_high"), "medium": t(lang, "risk_medium")}
    return m.get(level, t(lang, "risk_low"))


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def _cache_key(lang: str) -> str:
    return f"analysis_cache_{lang}"


def _get_cache(lang: str) -> dict | None:
    return st.session_state.get(_cache_key(lang))


def _set_cache(lang: str, data: dict):
    st.session_state[_cache_key(lang)] = data


# ---------------------------------------------------------------------------
# Page config — sidebar collapsed
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="PRLens", page_icon="🔍", layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------

st.markdown(
    f'<div class="prlens-hero"><h1>{t("en", "title")}</h1></div>',
    unsafe_allow_html=True,
)

st.markdown(f'<p class="prlens-muted">{t("en", "subtitle")}</p>', unsafe_allow_html=True)

lang_choice = st.selectbox(
    "语言 / Language", ["中文", "English"],
    key="lang_select",
)
lang = "zh" if lang_choice == "中文" else "en"
output_language = "zh" if lang == "zh" else "en"

# ---------------------------------------------------------------------------
# Input card
# ---------------------------------------------------------------------------

st.markdown('<div class="prlens-card">', unsafe_allow_html=True)
pr_url = st.text_input(
    t(lang, "pr_url_label"),
    placeholder=t(lang, "pr_url_placeholder"),
    label_visibility="visible",
)
c1, c2 = st.columns([1, 4])
with c1:
    analyze_clicked = st.button(t(lang, "analyze_btn"), type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Show cached result on language switch (no re-analyze)
# ---------------------------------------------------------------------------

cached = _get_cache(lang)

# ---------------------------------------------------------------------------
# Analyze handler
# ---------------------------------------------------------------------------

if analyze_clicked:
    if not pr_url.strip():
        st.warning(t(lang, "err_parse"))
    else:
        try:
            with st.status(t(lang, "ph_parsing"), expanded=True) as status:
                status.write(f"✓ {t(lang, 'ph_parsing')}")
                parsed = parse_github_pr_url(pr_url)

                status.write(f"⏳ {t(lang, 'ph_fetching_info')}")
                github_token = os.getenv("GITHUB_TOKEN") or None
                pr_info = fetch_pr_info(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )
                status.write(f"✓ {t(lang, 'ph_fetching_info')}")

                status.write(f"⏳ {t(lang, 'ph_fetching_files')}")
                changed_files = fetch_pr_files(
                    parsed.owner, parsed.repo, parsed.pull_number, token=github_token
                )
                status.write(f"✓ {t(lang, 'ph_fetching_files')}")

                status.write(f"✓ {t(lang, 'ph_building_diff')}")
                diff_context = build_diff_context(changed_files)

                llm_config = load_llm_config_from_env()

                status.write(f"⏳ {t(lang, 'ph_summary')}")
                summary_result = generate_pr_summary(
                    pr_info, diff_context, llm_config,
                    output_language=output_language,
                )
                status.write(f"✓ {t(lang, 'ph_summary')}")

                status.write(f"⏳ {t(lang, 'ph_risk')}")
                risk_result = analyze_pr_risks(
                    pr_info, diff_context, llm_config,
                    output_language=output_language,
                )
                status.write(f"✓ {t(lang, 'ph_risk')}")

                status.write(f"⏳ {t(lang, 'ph_suggestions')}")
                review_suggestions_result = generate_review_suggestions(
                    pr_info=pr_info,
                    diff_context=diff_context,
                    risk_result=risk_result,
                    llm_config=llm_config,
                    output_language=output_language,
                )
                status.write(f"✓ {t(lang, 'ph_suggestions')}")
                status.update(label=t(lang, "ph_done"), state="complete")

            # Cache the result under current language
            _set_cache(lang, {
                "pr_info": pr_info,
                "changed_files": changed_files,
                "diff_context": diff_context,
                "summary_result": summary_result,
                "risk_result": risk_result,
                "review_suggestions_result": review_suggestions_result,
            })
            cached = _get_cache(lang)

        except PRUrlParseError:
            st.error(t(lang, "err_parse"))
            cached = None
        except GitHubClientError as e:
            st.error(t(lang, "err_github") + f"\n\n({e})")
            cached = None
        except LLMConfigError:
            st.error(t(lang, "err_llm_config"))
            cached = None
        except LLMClientError as e:
            st.error(t(lang, "err_llm") + f"\n\n({e})")
            cached = None
        except SummaryAnalyzerError as e:
            st.error(t(lang, "err_summary") + f"\n\n({e})")
            cached = None
        except RiskAnalyzerError as e:
            st.error(t(lang, "err_risk") + f"\n\n({e})")
            cached = None
        except ReviewSuggestionError as e:
            st.error(t(lang, "err_suggestion") + f"\n\n({e})")
            cached = None
        except ValueError as e:
            st.error(t(lang, "err_input") + f"\n\n({e})")
            cached = None
        except Exception as e:
            st.error(t(lang, "err_unexpected") + f"\n\n({e})")
            cached = None


# ---------------------------------------------------------------------------
# Report builder (export helper)
# ---------------------------------------------------------------------------

def _build_report_md(lang: str, pr_info, summary_result, risk_result, review_suggestions_result) -> str:
    lines = [t(lang, "export_heading"), ""]

    lines.append(t(lang, "export_overview"))
    lines.append(t(lang, "export_title_row", title=pr_info.title))
    lines.append(t(lang, "export_status_row", status=format_pr_status(pr_info, lang)))
    lines.append(t(lang, "export_author_row", author=pr_info.author))
    lines.append(t(lang, "export_files_row", files=pr_info.changed_files))
    lines.append(t(lang, "export_additions_row", additions=pr_info.additions))
    lines.append(t(lang, "export_deletions_row", deletions=pr_info.deletions))
    lines.append(t(lang, "export_commits_row", commits=pr_info.commits))
    lines.append("")

    if summary_result:
        lines.append(t(lang, "export_summary_title"))
        lines.append(t(lang, "export_summary"))
        lines.append(summary_result.summary)
        lines.append("")
        lines.append(t(lang, "export_main_changes"))
        for item in _none_if_empty(summary_result.main_changes, lang):
            lines.append(f"- {item}")
        lines.append("")
        lines.append(t(lang, "export_affected_areas"))
        for item in _none_if_empty(summary_result.affected_areas, lang):
            lines.append(f"- {item}")
        lines.append("")
        lines.append(t(lang, "export_uncertainties"))
        for item in _none_if_empty(summary_result.uncertainties, lang):
            lines.append(f"- {item}")
        lines.append("")

    if risk_result:
        lines.append(t(lang, "export_risk_title"))
        level = _risk_level_label(risk_result.overall_risk_level, lang)
        lines.append(t(lang, "export_risk_level", level=level))
        lines.append("")
        if risk_result.risk_items:
            lines.append(t(lang, "export_risk_items"))
            for i, ri in enumerate(risk_result.risk_items, 1):
                lines.append(f"**{i}.** [{ri.severity}] {ri.risk_type} - `{ri.file_path}`")
                lines.append(f"- Evidence: {ri.evidence}")
                lines.append(f"- Explanation: {ri.explanation}")
                lines.append(f"- Impact: {ri.impact or 'N/A'}")
                lines.append(f"- Suggestion: {ri.suggestion}")
                lines.append(f"- Confidence: {ri.confidence} | Need human check: {'Yes' if ri.need_human_check else 'No'}")
                lines.append("")
        else:
            lines.append(t(lang, "export_risk_none"))
            lines.append("")
        if risk_result.limitations:
            lines.append(t(lang, "export_risk_limitations"))
            for item in risk_result.limitations:
                lines.append(f"- {item}")
            lines.append("")

    if review_suggestions_result:
        lines.append(t(lang, "export_sug_title"))
        if review_suggestions_result.suggestions:
            for i, sug in enumerate(review_suggestions_result.suggestions, 1):
                lines.append(f"**{i}.** [{sug.priority}] {sug.title}")
                lines.append(f"- File: `{sug.file_path}`")
                lines.append(f"- Problem: {sug.problem}")
                lines.append(f"- Evidence: {sug.evidence}")
                lines.append(f"- Suggestion: {sug.suggestion}")
                lines.append(f"- Copyable Comment: {sug.copy_text}")
                lines.append("")
        else:
            lines.append(t(lang, "export_sug_none"))
            lines.append("")

    lines.append(t(lang, "export_footer"))
    return "\n".join(lines)


# ====================================================================
# Results display — from cache or live
# ====================================================================

if cached:
    pr_info = cached["pr_info"]
    changed_files = cached["changed_files"]
    diff_context = cached["diff_context"]
    summary_result = cached["summary_result"]
    risk_result = cached["risk_result"]
    review_suggestions_result = cached["review_suggestions_result"]

    # ---------- export button ----------
    col_exp, _ = st.columns([1, 4])
    with col_exp:
        report_md = _build_report_md(
            lang, pr_info, summary_result, risk_result, review_suggestions_result
        )
        st.download_button(
            t(lang, "export_btn"),
            data=report_md,
            file_name=t(lang, "export_filename"),
            mime="text/markdown",
            use_container_width=True,
        )

    # ---------- PR Overview ----------
    st.subheader(t(lang, "pr_overview"))
    st.markdown(f"**[{pr_info.title}]({pr_info.html_url})**")
    c_m = st.columns(6)
    c_m[0].metric(t(lang, "status"), format_pr_status(pr_info, lang))
    c_m[1].metric(t(lang, "author"), pr_info.author)
    c_m[2].metric(t(lang, "changed_files_label"), pr_info.changed_files)
    c_m[3].metric(t(lang, "additions"), f"+{pr_info.additions}")
    c_m[4].metric(t(lang, "deletions"), f"-{pr_info.deletions}")
    c_m[5].metric(t(lang, "commits"), pr_info.commits)
    if pr_info.body:
        with st.expander(t(lang, "pr_description")):
            st.write(pr_info.body)

    st.divider()

    # ---------- Changed Files ----------
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
                t(lang, "patch_col"): t(lang, "patch_yes") if f.patch else t(lang, "patch_no"),
            })
        st.dataframe(file_data, use_container_width=True, hide_index=True)
        if len(changed_files) > 50:
            st.caption(t(lang, "more_files", n=len(changed_files) - 50))

    with st.expander(t(lang, "diff_title"), expanded=False):
        dcols = st.columns(5)
        dcols[0].metric(t(lang, "total_files"), diff_context.total_files)
        dcols[1].metric(t(lang, "included"), diff_context.included_files)
        dcols[2].metric(t(lang, "skipped"), diff_context.skipped_files)
        dcols[3].metric(t(lang, "truncated"), diff_context.truncated_files)
        dcols[4].metric(t(lang, "chars"), f"{diff_context.original_total_chars} → {diff_context.processed_total_chars}")
        if diff_context.was_truncated:
            st.warning(t(lang, "truncated_warning"))
        if diff_context.warnings:
            for w in diff_context.warnings:
                st.info(w)
        else:
            st.caption(t(lang, "warnings_empty"))

    # ---------- AI Change Summary ----------
    if summary_result:
        st.subheader(t(lang, "summary_title"))
        st.markdown(summary_result.summary)
        cl, cr = st.columns(2)
        with cl:
            st.markdown(f"**{t(lang, 'main_changes')}**")
            for item in _none_if_empty(summary_result.main_changes, lang):
                st.markdown(f"- {item}")
        with cr:
            st.markdown(f"**{t(lang, 'affected_areas')}**")
            for item in _none_if_empty(summary_result.affected_areas, lang):
                st.markdown(f"- {item}")
        st.markdown(f"**{t(lang, 'uncertainties')}**")
        for item in _none_if_empty(summary_result.uncertainties, lang):
            st.markdown(f"- {item}")

    # ---------- Risk Analysis ----------
    if risk_result:
        st.subheader(t(lang, "risk_title"))
        badge = (
            f'<span class="{_risk_level_badge_class(risk_result.overall_risk_level)}">'
            f'{_risk_level_label(risk_result.overall_risk_level, lang)}</span>'
        )
        st.markdown(f"{t(lang, 'risk_level')}: {badge}", unsafe_allow_html=True)

        if not risk_result.risk_items:
            st.info(t(lang, "risk_none_found"))
        else:
            sorted_risks = sorted(risk_result.risk_items, key=lambda r: SEVERITY_ORDER.get(r.severity, 99))
            for i, ri in enumerate(sorted_risks, 1):
                sev_badge = (
                    f'<span class="{_risk_level_badge_class(ri.severity)}">'
                    f'{_risk_level_label(ri.severity, lang)}</span>'
                )
                with st.expander(f"{t(lang, 'risk_item_label')} {i}: {ri.risk_type} — {ri.file_path}  {sev_badge}"):
                    st.markdown(f"**{t(lang, 'file_label')}:** `{ri.file_path or t(lang, 'na')}`")
                    st.markdown(f"**{t(lang, 'evidence_label')}:** {ri.evidence or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'explanation_label')}:** {ri.explanation or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'impact_label')}:** {ri.impact or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'suggestion_label')}:** {ri.suggestion or t(lang, 'na')}")
                    st.caption(f"{t(lang, 'confidence_label')}: {ri.confidence} | {t(lang, 'need_human_label')}: {t(lang, 'yes') if ri.need_human_check else t(lang, 'no')}")

        if risk_result.limitations:
            st.markdown(f"**{t(lang, 'limitations_label')}**")
            for item in risk_result.limitations:
                st.markdown(f"- {item}")
        else:
            st.caption(f"{t(lang, 'limitations_label')}: {t(lang, 'none')}")

    # ---------- Review Suggestions ----------
    if review_suggestions_result:
        st.subheader(t(lang, "sug_title"))
        if not review_suggestions_result.suggestions:
            st.info(t(lang, "sug_none_found"))
        else:
            sorted_sugs = sorted(review_suggestions_result.suggestions, key=lambda s: PRIORITY_ORDER.get(s.priority, 99))
            for i, sug in enumerate(sorted_sugs, 1):
                prio_badge = (
                    f'<span class="{_risk_level_badge_class(sug.priority)}">'
                    f'{sug.priority.upper()}</span>'
                )
                with st.expander(f"{t(lang, 'sug_item_label')} {i}: {sug.title}  {prio_badge}"):
                    st.markdown(f"**{t(lang, 'file_label')}:** `{sug.file_path or t(lang, 'na')}`")
                    st.markdown(f"**{t(lang, 'sug_problem')}:** {sug.problem or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'evidence_label')}:** {sug.evidence or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'impact_label')}:** {sug.impact or t(lang, 'na')}")
                    st.markdown(f"**{t(lang, 'suggestion_label')}:** {sug.suggestion or t(lang, 'na')}")
                    st.caption(f"{t(lang, 'sug_source_type')}: {sug.source_risk_type or t(lang, 'na')} | {t(lang, 'need_human_label')}: {t(lang, 'yes') if sug.need_human_check else t(lang, 'no')}")
                    st.markdown(f"**{t(lang, 'sug_copy_label')}:**")
                    st.text_area("", value=sug.copy_text, height=120, key=f"copy_{i}", label_visibility="collapsed")

        if review_suggestions_result.limitations:
            st.markdown(f"**{t(lang, 'limitations_label')}**")
            for item in review_suggestions_result.limitations:
                st.markdown(f"- {item}")
        else:
            st.caption(f"{t(lang, 'limitations_label')}: {t(lang, 'none')}")


st.divider()
st.markdown(f'<p class="prlens-muted" style="font-size:0.82rem;">{t(lang, "footer")}</p>', unsafe_allow_html=True)
st.caption(t(lang, "footer_about"))
