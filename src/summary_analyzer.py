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


def build_summary_messages(pr_info, diff_context) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages for summary generation.

    Args:
        pr_info: PRInfo object from github_client.
        diff_context: DiffContext object from diff_processor.

    Returns:
        List of message dicts with "role" and "content" keys.
    """
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
        {"role": "system", "content": _SYSTEM_PROMPT},
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


def generate_pr_summary(pr_info, diff_context, llm_config: LLMConfig) -> SummaryResult:
    """Generate a PR change summary using the LLM.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        llm_config: LLMConfig for the model call.

    Returns:
        SummaryResult with the parsed summary.

    Raises:
        SummaryAnalyzerError / SummaryResponseParseError: On parse failures.
        LLMClientError / subclasses: On API failures (passed through).
    """
    messages = build_summary_messages(pr_info, diff_context)
    response = chat_completion(messages, llm_config)
    return parse_summary_response(response.content)
