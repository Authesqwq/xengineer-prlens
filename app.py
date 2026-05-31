"""
PRLens: AI PR Review Assistant -- Streamlit Demo.

Bilingual (中文 / English) single-page workflow with workspace sidebar,
analysis modes, session history, and report export.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    get_default_model_profile,
    get_model_name,
    get_model_profiles,
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
# CSS
# ---------------------------------------------------------------------------

CSS = """
<style>
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

.block-container { max-width: 1100px; padding-top: 1.5rem; padding-bottom: 3rem; }

.prlens-hero { padding: 0.5rem 0 0.25rem 0; }
.prlens-hero h1 { font-size: 2rem; font-weight: 700; margin: 0; }

.prlens-muted { color: #64748b; font-size: 0.9rem; }
.prlens-sidebar-title { font-size: 1.1rem; font-weight: 700; }

.prlens-badge {
    display: inline-block; padding: 4px 10px; border-radius: 999px;
    font-size: 0.78rem; font-weight: 600;
}
.prlens-badge-high { background: #fef2f2; color: #dc2626; }
.prlens-badge-medium { background: #fffbeb; color: #d97706; }
.prlens-badge-low { background: #f0fdf4; color: #16a34a; }

section[data-testid="stSidebar"] { background: #f8fafc; }
section[data-testid="stSidebar"] .stRadio label { font-size: 0.9rem; }
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
        "pr_url_label": "GitHub PR 链接",
        "pr_url_placeholder": "请输入公开 GitHub PR 链接，例如：https://github.com/owner/repo/pull/123",
        "analyze_btn": "开始分析",
        "sidebar_title": "PRLens",
        "lang_label": "语言",
        "mode_label": "分析模式",
        "mode_fast": "快速模式",
        "mode_standard": "标准模式",
        "mode_full": "完整模式",
        "mode_hint_fast": "仅生成变更总结，适合快速了解 PR 做了什么。",
        "mode_hint_standard": "生成变更总结和风险分析，适合常规 Review 前的快速检查。",
        "mode_hint_full": "生成变更总结、风险分析和 Review 建议，适合需要形成评论草稿的场景。",
        "mode_runs": "执行内容",
        "mode_skips": "不执行",
        "mode_runs_summary": "AI 变更总结",
        "mode_runs_risk": "风险分析",
        "mode_runs_sug": "Review 建议",
        "elapsed_format_s": "{sec:.1f} 秒",
        "elapsed_format_ms": "{min:.0f} 分 {sec:.1f} 秒",
        "elapsed_unknown": "未知",
        "analysis_time": "用时 {time}",
        "mode_colon": "模式",
        "mode_display": "{mode}",
        "history_label": "历史记录",
        "history_empty": "暂无历史记录",
        "clear_history": "清空历史",
        "export_btn": "导出报告",
        "export_filename": "prlens_report.md",
        "lang_stale": "当前结果来自历史记录，正文语言可能与当前界面语言不一致。如需当前语言版本，请重新点击「开始分析」。",
        "history_restored": "已从历史记录恢复该分析结果。",
        "mode_fast_risk_note": "当前为快速模式，未执行风险分析。",
        "mode_fast_sug_note": "当前为快速模式，未生成 Review 建议。",
        "mode_standard_sug_note": "当前为标准模式，未生成 Review 建议。如需建议，请切换到完整模式后重新分析。",
        "risks_count": "{n} 个风险",
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
        "export_summary_s": "### 变更总结",
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
        "step_parse_url": "解析 PR 链接",
        "step_fetch_pr": "获取 PR 信息",
        "step_fetch_files": "获取变更文件",
        "step_build_context": "构建 diff 上下文",
        "step_summary": "生成变更总结",
        "step_risk": "分析风险",
        "step_suggestions": "生成 Review 建议",
        "step_complete": "完成",
        "step_running_parse": "正在解析 PR 链接...",
        "step_running_fetch": "正在获取 PR 基本信息...",
        "step_running_files": "正在获取变更文件和 patch...",
        "step_running_context": "正在构建 diff 上下文...",
        "step_running_summary": "正在生成变更总结...",
        "step_running_risk": "正在分析潜在风险...",
        "step_running_suggestions": "正在生成 Review 建议...",
        "step_skipped_suggestions": "未发现具体风险项，跳过 Review 建议生成",
        "step_failed_at": "分析在「{stage}」阶段失败，请检查输入、网络、GitHub Token 或 LLM 配置。",
        "progress_title": "分析进度",
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
        "chars": "字符数变化",
        "chars_original": "原始字符数",
        "chars_processed": "处理后字符数",
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
        "pr_url_label": "GitHub PR URL",
        "pr_url_placeholder": "Enter a public GitHub PR URL, e.g. https://github.com/owner/repo/pull/123",
        "analyze_btn": "Analyze PR",
        "sidebar_title": "PRLens",
        "lang_label": "Language",
        "mode_label": "Analysis Mode",
        "mode_fast": "Fast",
        "mode_standard": "Standard",
        "mode_full": "Full",
        "mode_hint_fast": "Generates only the change summary. Best for quickly understanding what the PR does.",
        "mode_hint_standard": "Generates change summary and risk analysis. Best for a standard pre-review check.",
        "mode_hint_full": "Generates change summary, risk analysis, and review suggestions. Best when you need review comment drafts.",
        "mode_runs": "Will run",
        "mode_skips": "Will skip",
        "mode_runs_summary": "Change Summary",
        "mode_runs_risk": "Risk Analysis",
        "mode_runs_sug": "Review Suggestions",
        "elapsed_format_s": "{sec:.1f}s",
        "elapsed_format_ms": "{min:.0f}m {sec:.1f}s",
        "elapsed_unknown": "Unknown",
        "analysis_time": "{time}",
        "mode_colon": "Mode",
        "mode_display": "{mode}",
        "history_label": "History",
        "history_empty": "No history yet",
        "clear_history": "Clear History",
        "export_btn": "Export Report",
        "export_filename": "prlens_report.md",
        "lang_stale": "This result was restored from history. Its content language may differ from the current UI language. Click Analyze PR to regenerate it.",
        "history_restored": "This result was restored from history.",
        "mode_fast_risk_note": "Fast mode does not run risk analysis.",
        "mode_fast_sug_note": "Fast mode does not generate review suggestions.",
        "mode_standard_sug_note": "Standard mode does not generate review suggestions. Switch to Full mode and analyze again to generate suggestions.",
        "risks_count": "{n} risks",
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
        "export_summary_s": "### Summary",
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
        "step_parse_url": "Parse PR URL",
        "step_fetch_pr": "Fetch PR Info",
        "step_fetch_files": "Fetch Changed Files",
        "step_build_context": "Build Diff Context",
        "step_summary": "Generate Change Summary",
        "step_risk": "Analyze Risks",
        "step_suggestions": "Generate Review Suggestions",
        "step_complete": "Complete",
        "step_running_parse": "Parsing PR URL...",
        "step_running_fetch": "Fetching PR information...",
        "step_running_files": "Fetching changed files and patches...",
        "step_running_context": "Building diff context...",
        "step_running_summary": "Generating change summary...",
        "step_running_risk": "Analyzing potential risks...",
        "step_running_suggestions": "Generating review suggestions...",
        "step_skipped_suggestions": "No concrete risk items found. Skipping review suggestion generation.",
        "step_failed_at": "Analysis failed at \"{stage}\". Please check the input, network, GitHub token, or LLM configuration.",
        "progress_title": "Analysis Progress",
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
        "chars": "Character Count Change",
        "chars_original": "Original Characters",
        "chars_processed": "Processed Characters",
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
# Helpers
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
MODE_KEYS = {"快速模式": "fast", "标准模式": "standard", "完整模式": "full",
             "Fast": "fast", "Standard": "standard", "Full": "full"}

HISTORY_MAX = 10


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
    return items if items else [t(lang, "none")]


def _badge_class(level: str) -> str:
    m = {"high": "prlens-badge prlens-badge-high",
         "medium": "prlens-badge prlens-badge-medium"}
    return m.get(level, "prlens-badge prlens-badge-low")


def _risk_label(level: str, lang: str) -> str:
    m = {"high": t(lang, "risk_high"), "medium": t(lang, "risk_medium")}
    return m.get(level, t(lang, "risk_low"))


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_report_md(lang, pr_info, summary_result, risk_result,
                     review_suggestions_result, analysis_mode=None, elapsed_seconds=None) -> str:
    lines = [t(lang, "export_heading"), ""]
    lines.append(t(lang, "export_overview"))
    if analysis_mode:
        lines.append(f"- {t(lang, 'mode_colon')}: {_mode_display_name(analysis_mode, lang)}")
    if elapsed_seconds is not None:
        lines.append(f"- {t(lang, 'analysis_time', time=format_elapsed_time(elapsed_seconds, lang))}")
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
        lines.append(t(lang, "export_summary_s"))
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
        lines.append(t(lang, "export_risk_level", level=_risk_label(risk_result.overall_risk_level, lang)))
        lines.append("")
        if risk_result.risk_items:
            lines.append(t(lang, "export_risk_items"))
            for i, ri in enumerate(risk_result.risk_items, 1):
                lines.append(f"**{i}.** [{ri.severity}] {ri.risk_type} - `{ri.file_path}`")
                lines.append(f"- {t(lang, 'evidence_label')}: {ri.evidence}")
                lines.append(f"- {t(lang, 'explanation_label')}: {ri.explanation}")
                lines.append(f"- {t(lang, 'impact_label')}: {ri.impact or 'N/A'}")
                lines.append(f"- {t(lang, 'suggestion_label')}: {ri.suggestion}")
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
                lines.append(f"- {t(lang, 'file_label')}: `{sug.file_path}`")
                lines.append(f"- {t(lang, 'sug_problem')}: {sug.problem}")
                lines.append(f"- {t(lang, 'evidence_label')}: {sug.evidence}")
                lines.append(f"- {t(lang, 'suggestion_label')}: {sug.suggestion}")
                lines.append("")
        else:
            lines.append(t(lang, "export_sug_none"))
            lines.append("")
    lines.append(t(lang, "export_footer"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def _make_history_key(pr_url: str, lang: str, mode: str) -> str:
    return f"{pr_url}|{lang}|{mode}"


def _add_to_history(entry: dict):
    history = st.session_state.setdefault("analysis_history", [])
    key = _make_history_key(entry["url"], entry["language"], entry["analysis_mode"])
    history = [h for h in history if _make_history_key(h["url"], h["language"], h["analysis_mode"]) != key]
    history.insert(0, entry)
    st.session_state["analysis_history"] = history[:HISTORY_MAX]


def format_elapsed_time(seconds, lang: str) -> str:
    if seconds is None:
        return t(lang, "elapsed_unknown")
    s = float(seconds)
    if s < 60:
        return t(lang, "elapsed_format_s", sec=s)
    m = int(s // 60)
    sec = s % 60
    return t(lang, "elapsed_format_ms", min=m, sec=sec)


def _mode_hint_for_mode(mode_key: str, lang: str) -> str:
    hints = {"fast": "mode_hint_fast", "standard": "mode_hint_standard", "full": "mode_hint_full"}
    return t(lang, hints.get(mode_key, "mode_hint_standard"))


def _mode_display_name(mode_key: str, lang: str) -> str:
    names = {"fast": t(lang, "mode_fast"), "standard": t(lang, "mode_standard"), "full": t(lang, "mode_full")}
    return names.get(mode_key, mode_key)


def _history_item_label(entry: dict, lang: str) -> str:
    try:
        parsed = parse_github_pr_url(entry["url"])
        short = f"{parsed.owner}/{parsed.repo} #{parsed.pull_number}"
    except Exception:
        short = entry["url"]
    parts = [short]
    mode_key = entry.get("analysis_mode", "")
    if mode_key:
        parts.append(_mode_display_name(mode_key, lang))
    if entry.get("risk_level"):
        parts.append(_risk_label(entry["risk_level"], lang))
    if entry.get("elapsed_seconds") is not None:
        parts.append(format_elapsed_time(entry["elapsed_seconds"], lang))
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Progress steps
# ---------------------------------------------------------------------------

_STEP_KEYS_ALL = ["parse_url", "fetch_pr", "fetch_files", "build_context", "summary", "risk", "suggestions"]
_STEP_KEY_LABEL = {
    "parse_url": "step_parse_url", "fetch_pr": "step_fetch_pr",
    "fetch_files": "step_fetch_files", "build_context": "step_build_context",
    "summary": "step_summary", "risk": "step_risk", "suggestions": "step_suggestions",
}
_STEP_KEY_RUNNING = {
    "parse_url": "step_running_parse", "fetch_pr": "step_running_fetch",
    "fetch_files": "step_running_files", "build_context": "step_running_context",
    "summary": "step_running_summary", "risk": "step_running_risk",
    "suggestions": "step_running_suggestions",
}
_MODE_STEP_KEYS = {
    "fast": ["parse_url", "fetch_pr", "fetch_files", "build_context", "summary"],
    "standard": ["parse_url", "fetch_pr", "fetch_files", "build_context", "summary", "risk"],
    "full": ["parse_url", "fetch_pr", "fetch_files", "build_context", "summary", "risk", "suggestions"],
}


def build_analysis_steps(analysis_mode: str, lang: str) -> list[dict]:
    keys = _MODE_STEP_KEYS.get(analysis_mode, _MODE_STEP_KEYS["standard"])
    return [{"key": k, "label": t(lang, _STEP_KEY_LABEL[k])} for k in keys]


def render_progress_steps(steps, current_key=None, completed_keys=None,
                          skipped_keys=None, failed_key=None) -> str:
    completed_keys = set(completed_keys or [])
    skipped_keys = set(skipped_keys or [])
    lines = []
    for step in steps:
        key = step["key"]
        if failed_key and key == failed_key:
            lines.append(f'✕ {step["label"]}')
        elif key in completed_keys:
            lines.append(f'✓ {step["label"]}')
        elif key == current_key:
            lines.append(f'▶ {step["label"]}')
        elif key in skipped_keys:
            lines.append(f'⚠ {step["label"]}')
        else:
            lines.append(f'○ {step["label"]}')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PRLens", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

# init session state
if "analysis_history" not in st.session_state:
    st.session_state["analysis_history"] = []
if "analysis_mode" not in st.session_state:
    st.session_state["analysis_mode"] = "standard"

# ====================================================================
# SIDEBAR — workspace
# ====================================================================

with st.sidebar:
    st.markdown(f'<p class="prlens-sidebar-title">{t("en", "sidebar_title")}</p>', unsafe_allow_html=True)
    st.divider()

    # Language
    lang_choice = st.radio(
        t("en", "lang_label"), ["中文", "English"],
        key="sidebar_lang",
    )
    lang = "zh" if lang_choice == "中文" else "en"
    output_language = "zh" if lang == "zh" else "en"

    st.divider()

    # Analysis mode
    st.caption(t(lang, "mode_label"))
    mode_options_zh = ["快速模式", "标准模式", "完整模式"]
    mode_options_en = ["Fast", "Standard", "Full"]
    mode_options = mode_options_zh if lang == "zh" else mode_options_en
    selected_mode = st.radio(
        t(lang, "mode_label"),
        mode_options,
        index=1,  # default: standard
        key="analysis_mode_radio",
        label_visibility="collapsed",
    )
    st.session_state["analysis_mode"] = MODE_KEYS.get(selected_mode, "standard")
    mode_key = st.session_state["analysis_mode"]
    st.caption(_mode_hint_for_mode(mode_key, lang))

    st.divider()

    # Model profile
    profiles = get_model_profiles()
    default_profile = get_default_model_profile()
    if "model_profile" not in st.session_state:
        st.session_state["model_profile"] = default_profile
    profile_options = {"fast": "快速模型" if lang == "zh" else "Fast model",
                       "quality": "高质量模型" if lang == "zh" else "Quality model"}
    selected_profile = st.radio(
        "模型档位" if lang == "zh" else "Model Profile",
        list(profile_options.keys()),
        format_func=lambda k: profile_options[k],
        index=0 if st.session_state["model_profile"] == "fast" else 1,
        key="model_profile_radio",
        label_visibility="visible",
    )
    st.session_state["model_profile"] = selected_profile
    st.caption(profiles[selected_profile][f"description_{lang}"])

    st.divider()

    # History
    st.caption(t(lang, "history_label"))
    history = st.session_state.get("analysis_history", [])
    if history:
        for i, entry in enumerate(history):
            label = _history_item_label(entry, lang)
            if st.button(label, key=f"hist_{i}", use_container_width=True):
                st.session_state["analysis_result"] = entry["result"]
                st.session_state["result_lang"] = entry.get("language", output_language)
                st.session_state["result_from_history"] = True
                st.session_state["pr_url_input"] = entry["url"]
                st.rerun()
    else:
        st.caption(t(lang, "history_empty"))

    st.divider()

    # Actions
    cached = st.session_state.get("analysis_result")
    if cached:
        summary = cached.get("summary_result")
        risk = cached.get("risk_result")
        sug = cached.get("review_suggestions_result")
        pi = cached.get("pr_info")
        if pi and summary:
            report_md = _build_report_md(
                lang, pi, summary, risk, sug,
                analysis_mode=cached.get("analysis_mode"),
                elapsed_seconds=cached.get("elapsed_seconds"),
            )
            st.download_button(
                t(lang, "export_btn"), data=report_md,
                file_name=t(lang, "export_filename"), mime="text/markdown",
                use_container_width=True,
            )

    if st.button(t(lang, "clear_history"), use_container_width=True):
        st.session_state["analysis_history"] = []
        st.rerun()

# ====================================================================
# MAIN PAGE
# ====================================================================

st.markdown(f'<div class="prlens-hero"><h1>{t(lang, "title")}</h1></div>', unsafe_allow_html=True)
st.markdown(f'<p class="prlens-muted">{t(lang, "subtitle")}</p>', unsafe_allow_html=True)

with st.container(border=True):
    pr_url = st.text_input(
        t(lang, "pr_url_label"),
        placeholder=t(lang, "pr_url_placeholder"),
        key="pr_url_input",
    )
    cc1, _ = st.columns([1, 4])
    with cc1:
        analyze_clicked = st.button(t(lang, "analyze_btn"), type="primary", use_container_width=True)

# ====================================================================
# Analyze
# ====================================================================

if analyze_clicked:
    if not pr_url.strip():
        st.warning(t(lang, "err_parse"))
    else:
        analysis_mode = st.session_state.get("analysis_mode", "standard")
        do_risk = analysis_mode in ("standard", "full")
        do_suggestions = analysis_mode == "full"
        start_time = time.perf_counter()

        summary_result = None
        risk_result = None
        review_suggestions_result = None
        parsed = None
        github_token = None

        steps = build_analysis_steps(analysis_mode, lang)
        completed = set()
        skipped = set()
        current = None
        failed = None

        progress_placeholder = st.empty()
        bar = st.progress(0)

        def _update_progress():
            progress_placeholder.markdown(
                f"**{t(lang, 'progress_title')}**\n\n"
                + render_progress_steps(steps, current, completed, skipped, failed)
            )
            total = len(steps)
            done = len(completed) + len(skipped)
            bar.progress(min(done / total, 1.0) if total else 0)

        try:
            # Step: parse URL
            current = "parse_url"
            _update_progress()
            parsed = parse_github_pr_url(pr_url)
            completed.add("parse_url")

            # Step: fetch PR info
            current = "fetch_pr"
            _update_progress()
            github_token = os.getenv("GITHUB_TOKEN") or None
            pr_info = fetch_pr_info(parsed.owner, parsed.repo, parsed.pull_number, token=github_token)
            completed.add("fetch_pr")

            # Step: fetch files
            current = "fetch_files"
            _update_progress()
            changed_files = fetch_pr_files(parsed.owner, parsed.repo, parsed.pull_number, token=github_token)
            completed.add("fetch_files")

            # Step: build diff context
            current = "build_context"
            _update_progress()
            diff_context = build_diff_context(changed_files)
            completed.add("build_context")

            # LLM config
            llm_config = load_llm_config_from_env()
            model_profile = st.session_state.get("model_profile", "fast")
            model_name = get_model_name(model_profile)
            if model_name:
                llm_config.model = model_name

            # Step: summary + risk (parallel)
            risk_result = None
            if do_risk:
                current = "summary"
                _update_progress()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    sf = pool.submit(generate_pr_summary, pr_info, diff_context, llm_config, output_language=output_language)
                    rf = pool.submit(analyze_pr_risks, pr_info, diff_context, llm_config, output_language=output_language)
                    for f in as_completed([sf, rf]):
                        if f == sf:
                            try:
                                summary_result = sf.result()
                            except Exception:
                                summary_result = generate_pr_summary(pr_info, diff_context, llm_config, output_language=output_language)
                        else:
                            try:
                                risk_result = rf.result()
                            except Exception:
                                risk_result = analyze_pr_risks(pr_info, diff_context, llm_config, output_language=output_language)
                completed.add("summary")
                completed.add("risk")
                current = "summary"
                _update_progress()
            else:
                current = "summary"
                _update_progress()
                summary_result = generate_pr_summary(pr_info, diff_context, llm_config, output_language=output_language)
                completed.add("summary")

            # Step: suggestions
            if do_suggestions:
                current = "suggestions"
                _update_progress()
                if risk_result and risk_result.risk_items:
                    review_suggestions_result = generate_review_suggestions(
                        pr_info=pr_info, diff_context=diff_context,
                        risk_result=risk_result, llm_config=llm_config,
                        output_language=output_language,
                    )
                    completed.add("suggestions")
                else:
                    review_suggestions_result = generate_review_suggestions(
                        pr_info=pr_info, diff_context=diff_context,
                        risk_result=risk_result, llm_config=llm_config,
                        output_language=output_language,
                    )
                    skipped.add("suggestions")

            # Done
            current = None
            _update_progress()

            elapsed_seconds = time.perf_counter() - start_time
            progress_placeholder.markdown(
                f"**{t(lang, 'ph_done')}** — "
                f"{t(lang, 'analysis_time', time=format_elapsed_time(elapsed_seconds, lang))}"
            )

            result_data = {
                "pr_info": pr_info,
                "changed_files": changed_files,
                "diff_context": diff_context,
                "summary_result": summary_result,
                "risk_result": risk_result,
                "review_suggestions_result": review_suggestions_result,
                "elapsed_seconds": elapsed_seconds,
                "analysis_mode": analysis_mode,
                "model_profile": model_profile,
                "model_name": model_name,
            }
            st.session_state["analysis_result"] = result_data
            st.session_state["result_lang"] = output_language
            st.session_state["result_from_history"] = False

            risk_level = risk_result.overall_risk_level if risk_result else None
            risk_count = len(risk_result.risk_items) if risk_result and risk_result.risk_items else 0
            _add_to_history({
                "url": pr_url,
                "owner": parsed.owner, "repo": parsed.repo,
                "pull_number": parsed.pull_number,
                "title": pr_info.title,
                "status": format_pr_status(pr_info, lang),
                "risk_level": risk_level,
                "risk_count": risk_count,
                "language": output_language,
                "analysis_mode": analysis_mode,
                "model_profile": model_profile,
                "model_name": model_name,
                "created_at": time.strftime("%H:%M:%S"),
                "elapsed_seconds": elapsed_seconds,
                "result": result_data,
            })

        except PRUrlParseError:
            failed = current or "parse_url"
            _update_progress()
            st.error(t(lang, "err_parse"))
        except GitHubClientError as e:
            failed = current or "fetch_pr"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, _STEP_KEY_LABEL.get(failed, "step_fetch_pr"))))
        except LLMConfigError:
            failed = current or "summary"
            _update_progress()
            st.error(t(lang, "err_llm_config"))
        except LLMClientError as e:
            failed = current or "summary"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, _STEP_KEY_LABEL.get(failed, "step_summary"))))
        except SummaryAnalyzerError as e:
            failed = "summary"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, "step_summary")))
        except RiskAnalyzerError as e:
            failed = "risk"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, "step_risk")))
        except ReviewSuggestionError as e:
            failed = "suggestions"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, "step_suggestions")))
        except ValueError as e:
            failed = current or "parse_url"
            _update_progress()
            st.error(t(lang, "err_input") + f"\n\n({e})")
        except Exception as e:
            failed = current or "parse_url"
            _update_progress()
            st.error(t(lang, "step_failed_at", stage=t(lang, _STEP_KEY_LABEL.get(failed, "step_parse_url"))))

# ====================================================================
# Results display
# ====================================================================

cached = st.session_state.get("analysis_result")
if cached:
    pr_info = cached["pr_info"]
    changed_files = cached["changed_files"]
    diff_context = cached["diff_context"]
    summary_result = cached["summary_result"]
    risk_result = cached["risk_result"]
    review_suggestions_result = cached["review_suggestions_result"]

    result_lang = st.session_state.get("result_lang", lang)
    from_history = st.session_state.get("result_from_history", False)

    if from_history:
        st.info(t(lang, "history_restored"))
        if result_lang != output_language:
            st.info(t(lang, "lang_stale"))

    # ---------- PR Overview ----------
    st.subheader(t(lang, "pr_overview"))
    elapsed = cached.get("elapsed_seconds")
    analysis_mode = cached.get("analysis_mode", st.session_state.get("analysis_mode", "standard"))
    if elapsed is not None:
        time_str = format_elapsed_time(elapsed, lang)
        model_label = cached.get("model_name", "")
        st.caption(f"{t(lang, 'analysis_time', time=time_str)} · {t(lang, 'mode_colon')}: {_mode_display_name(analysis_mode, lang)} · 模型: {model_label}" if lang == "zh" else f"{t(lang, 'analysis_time', time=time_str)} · {t(lang, 'mode_colon')}: {_mode_display_name(analysis_mode, lang)} · Model: {model_label}")
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
        dcols = st.columns(4)
        dcols[0].metric(t(lang, "total_files"), diff_context.total_files)
        dcols[1].metric(t(lang, "included"), diff_context.included_files)
        dcols[2].metric(t(lang, "skipped"), diff_context.skipped_files)
        dcols[3].metric(t(lang, "truncated"), diff_context.truncated_files)
        st.markdown(f"**{t(lang, 'chars')}**")
        st.markdown(
            f"{t(lang, 'chars_original')}: {diff_context.original_total_chars}  "
            f"→  {t(lang, 'chars_processed')}: {diff_context.processed_total_chars}"
        )
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
            f'<span class="{_badge_class(risk_result.overall_risk_level)}">'
            f'{_risk_label(risk_result.overall_risk_level, lang)}</span>'
        )
        st.markdown(f"{t(lang, 'risk_level')}: {badge}", unsafe_allow_html=True)
        if not risk_result.risk_items:
            st.info(t(lang, "risk_none_found"))
        else:
            sorted_risks = sorted(risk_result.risk_items, key=lambda r: SEVERITY_ORDER.get(r.severity, 99))
            for i, ri in enumerate(sorted_risks, 1):
                sev_badge = f'<span class="{_badge_class(ri.severity)}">{_risk_label(ri.severity, lang)}</span>'
                with st.expander(f"{t(lang, 'risk_item_label')} {i}: {ri.risk_type} - {ri.file_path}  {sev_badge}"):
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
    else:
        st.subheader(t(lang, "risk_title"))
        st.info(t(lang, "mode_fast_risk_note"))

    # ---------- Review Suggestions ----------
    if review_suggestions_result:
        st.subheader(t(lang, "sug_title"))
        if not review_suggestions_result.suggestions:
            st.info(t(lang, "sug_none_found"))
        else:
            sorted_sugs = sorted(review_suggestions_result.suggestions, key=lambda s: PRIORITY_ORDER.get(s.priority, 99))
            for i, sug in enumerate(sorted_sugs, 1):
                prio_badge = f'<span class="{_badge_class(sug.priority)}">{sug.priority.upper()}</span>'
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
    else:
        st.subheader(t(lang, "sug_title"))
        analysis_mode = st.session_state.get("analysis_mode", "standard")
        if analysis_mode == "fast":
            st.info(t(lang, "mode_fast_sug_note"))
        else:
            st.info(t(lang, "mode_standard_sug_note"))

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.markdown(f'<p class="prlens-muted" style="font-size:0.82rem;">{t(lang, "footer")}</p>', unsafe_allow_html=True)
st.caption(t(lang, "footer_about"))
