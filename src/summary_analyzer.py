"""PR change summary generation via LLM."""

import json
import re
from dataclasses import dataclass

from src.llm_client import LLMConfig, LLMResponse, chat_completion


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SummaryResult:
    summary: str
    main_changes: list[str]
    affected_areas: list[str]
    uncertainties: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SummaryAnalyzerError(RuntimeError):
    pass


class SummaryResponseParseError(SummaryAnalyzerError):
    pass


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a code review assistant. Only use the provided PR information and diff \
context to generate a summary. Do not supplement with knowledge outside the \
provided context. Mark anything uncertain under "uncertainties". Do not \
output whether the PR should be merged.
Return only valid JSON.
Use exactly these top-level keys: summary, main_changes, affected_areas, uncertainties.
The field summary must be a string.
The fields main_changes, affected_areas, and uncertainties must always be \
JSON arrays. If there is no item, return [].
Do not use alternative field names such as overview, pr_summary, change_summary, or result."""


def _language_instruction(lang: str) -> str:
    if lang == "zh":
        return (
            "Write all natural language fields in Simplified Chinese. "
            "Keep file paths, code identifiers, GitHub labels, action names, "
            "branch names, and schema keys unchanged. The fields summary, "
            "main_changes, affected_areas, and uncertainties must use Chinese "
            "natural language when possible."
        )
    return "Write all natural language fields in English."


def build_summary_messages(pr_info, diff_context, output_language: str = "en") -> list[dict[str, str]]:
    """Build OpenAI-compatible messages for summary generation.

    Args:
        pr_info: PRInfo object from github_client.
        diff_context: DiffContext object from diff_processor.
        output_language: "en" or "zh" — language for natural language output.

    Returns:
        List of message dicts with "role" and "content" keys.
    """
    system_prompt = _SYSTEM_PROMPT + "\n" + _language_instruction(output_language)

    user_content = (
        f"PR Title: {pr_info.title}\n"
        f"PR Body: {pr_info.body or '(empty)'}\n"
        f"Author: {pr_info.author}\n"
        f"State: {pr_info.state}\n"
        f"Additions: {pr_info.additions}\n"
        f"Deletions: {pr_info.deletions}\n"
        f"Changed Files: {pr_info.changed_files}\n"
        f"Diff Context:\n{diff_context.content}"
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_FENCE_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)

_EMPTY_STR_VALUES = {"", "none", "无", "n/a"}

_SUMMARY_ALIASES = [
    "summary",
    "pr_summary",
    "change_summary",
    "overview",
    "description",
    "result_summary",
    "analysis_summary",
]

_UNWRAP_KEYS = ["result", "data", "summary_result"]


def _get_summary_text(data: dict) -> str:
    """Extract summary text from data, trying known alias keys in order.

    Args:
        data: Parsed JSON dict.

    Returns:
        Non-empty summary string.

    Raises:
        SummaryResponseParseError: If no alias is found or the value is invalid.
    """
    for key in _SUMMARY_ALIASES:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
            continue
        raise SummaryResponseParseError(
            f'Field "{key}" must be a string, got {type(value).__name__}. '
            f"Available keys: {', '.join(data.keys())}"
        )

    raise SummaryResponseParseError(
        f'Missing required field "summary" in model response. '
        f"Available keys: {', '.join(data.keys())}"
    )


def _normalize_string_list_field(value, field_name: str) -> list[str]:
    """Normalize a field that should be a list of strings.

    Handles LLMs that return a single string instead of an array.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() in _EMPTY_STR_VALUES:
            return []
        return [stripped]
    raise SummaryResponseParseError(
        f'Field "{field_name}" must be a list or string, got {type(value).__name__}'
    )


def parse_summary_response(content: str) -> SummaryResult:
    """Parse a model JSON output into SummaryResult.

    Handles both raw JSON and fenced ```json code blocks.

    Args:
        content: Raw model output string.

    Returns:
        SummaryResult with parsed fields.

    Raises:
        SummaryResponseParseError: If parsing fails or required fields are missing.
    """
    if not content or not content.strip():
        raise SummaryResponseParseError("Model returned empty content.")

    text = content.strip()

    # Try fenced code block extraction first
    match = _FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise SummaryResponseParseError(f"Failed to parse JSON: {e}") from e

    if not isinstance(data, dict):
        raise SummaryResponseParseError(f"Expected JSON object, got {type(data).__name__}")

    # Unwrap single-level nesting (e.g. {"result": {...}})
    for key in _UNWRAP_KEYS:
        if key in data and isinstance(data[key], dict):
            data = data[key]
            break

    summary_text = _get_summary_text(data)

    main_changes = _normalize_string_list_field(
        data.get("main_changes", []), "main_changes"
    )
    affected_areas = _normalize_string_list_field(
        data.get("affected_areas", []), "affected_areas"
    )
    uncertainties = _normalize_string_list_field(
        data.get("uncertainties", []), "uncertainties"
    )

    return SummaryResult(
        summary=summary_text,
        main_changes=main_changes,
        affected_areas=affected_areas,
        uncertainties=uncertainties,
        raw_response=content,
    )


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def _build_deterministic_summary(pr_info, diff_context, output_language: str = "en") -> SummaryResult:
    """Build a deterministic fallback summary from PR metadata."""
    zh = output_language == "zh"
    note = (
        "摘要生成未能获得稳定结构化输出，以下为基于 PR 元信息和 diff 统计生成的降级摘要。"
        if zh else
        "Summary generation did not produce stable structured output. "
        "The following is a deterministic fallback based on PR metadata and diff statistics."
    )
    changes_desc = (
        f"该 PR 修改了 {diff_context.total_files} 个文件"
        if zh else
        f"This PR modifies {diff_context.total_files} file(s)"
    )
    if pr_info.additions or pr_info.deletions:
        changes_desc += (
            f"，新增 {pr_info.additions} 行，删除 {pr_info.deletions} 行。"
            if zh else
            f", adding {pr_info.additions} and removing {pr_info.deletions} lines."
        )
    else:
        changes_desc += "。"

    summary = (
        f"{note}\n\n"
        f"{'标题' if zh else 'Title'}: {pr_info.title}\n"
        f"{'作者' if zh else 'Author'}: {pr_info.author}\n"
        f"{'描述' if zh else 'Description'}: {pr_info.body or ('(空)' if zh else '(empty)')}\n"
        f"{changes_desc}"
    )
    return SummaryResult(
        summary=summary,
        main_changes=[],
        affected_areas=[],
        uncertainties=[note],
        raw_response="",
    )


def generate_pr_summary(pr_info, diff_context, llm_config: LLMConfig,
                        output_language: str = "en") -> SummaryResult:
    """Generate a PR change summary using the LLM, with retry and fallback.

    On empty content or JSON parse failure, retries once. If retry also fails
    and raw text is available, uses it as degraded summary. Otherwise returns
    deterministic fallback based on PR metadata.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        llm_config: LLMConfig for the model call.
        output_language: "en" or "zh".

    Returns:
        SummaryResult — always returns a result, never raises on parse failure.
    """
    messages = build_summary_messages(pr_info, diff_context, output_language=output_language)
    try:
        response = chat_completion(messages, llm_config)
        if not response.content or not response.content.strip():
            return _retry_summary(messages, pr_info, diff_context, llm_config, output_language)
        return parse_summary_response(response.content)
    except (LLMClientError, SummaryResponseParseError):
        return _retry_summary(messages, pr_info, diff_context, llm_config, output_language)


def _retry_summary(messages, pr_info, diff_context, llm_config: LLMConfig,
                   output_language: str) -> SummaryResult:
    zh = output_language == "zh"
    retry_msg = (
        "上一条回复是空内容或无法解析为 JSON。请只返回一个合法 JSON 对象。"
        if zh else
        "The previous response was empty or could not be parsed as JSON. "
        "Return only a valid JSON object."
    )
    try:
        retry_resp = chat_completion(messages + [{"role": "user", "content": retry_msg}], llm_config)
        if retry_resp.content and retry_resp.content.strip():
            try:
                return parse_summary_response(retry_resp.content)
            except SummaryResponseParseError:
                pass  # Fall through to raw text fallback
    except LLMClientError:
        pass

    return _build_deterministic_summary(pr_info, diff_context, output_language)
