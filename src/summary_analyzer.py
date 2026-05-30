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
output whether the PR should be merged. Output must be JSON only."""


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

    main_changes = data.get("main_changes", [])
    affected_areas = data.get("affected_areas", [])
    uncertainties = data.get("uncertainties", [])

    for name, value in [("main_changes", main_changes), ("affected_areas", affected_areas),
                        ("uncertainties", uncertainties)]:
        if not isinstance(value, list):
            raise SummaryResponseParseError(
                f'Field "{name}" must be a list, got {type(value).__name__}'
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
