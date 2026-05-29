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
output whether the PR should be merged. Output must be JSON only.
The fields main_changes, affected_areas, and uncertainties must always be \
JSON arrays. If there is no item, return an empty array []."""


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

    if "summary" not in data:
        raise SummaryResponseParseError('Missing required field "summary" in model response')

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
        summary=data["summary"],
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
