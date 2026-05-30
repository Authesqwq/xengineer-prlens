"""Structured Review suggestion generation from risk analysis results."""

import json
import re
from dataclasses import dataclass

from src.llm_client import LLMConfig, chat_completion


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ReviewSuggestion:
    title: str
    priority: str
    file_path: str
    problem: str
    evidence: str
    impact: str
    suggestion: str
    copy_text: str
    source_risk_type: str
    need_human_check: bool


@dataclass
class ReviewSuggestionResult:
    suggestions: list[ReviewSuggestion]
    limitations: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ReviewSuggestionError(RuntimeError):
    pass


class ReviewSuggestionParseError(ReviewSuggestionError):
    pass


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a Pull Request review suggestion generator. Only use the provided PR \
information, diff context, and risk analysis results to create structured \
review suggestions. Do not supplement with knowledge outside the provided \
context. Do not judge whether the PR should be merged. Do not force \
suggestions — if no risks are provided, return empty suggestions.

Every suggestion must contain evidence and an actionable suggestion.
The copy_text field should be suitable as a PR review comment draft.
Return only valid JSON. Use exactly these top-level keys: suggestions, limitations.

priority must be one of: high, medium, low.

Format:
{
  "suggestions": [
    {
      "title": "...",
      "priority": "medium",
      "file_path": "src/example.py",
      "problem": "...",
      "evidence": "...",
      "impact": "...",
      "suggestion": "...",
      "copy_text": "...",
      "source_risk_type": "logic",
      "need_human_check": true
    }
  ],
  "limitations": []
}"""


def _language_instruction(lang: str) -> str:
    if lang == "zh":
        return (
            "Write title, problem, evidence, impact, suggestion, copy_text, and "
            "limitations in Simplified Chinese when possible. Keep file_path, "
            "source_risk_type, priority, schema keys, code identifiers, and GitHub "
            "labels unchanged. copy_text should be a Chinese review comment draft."
        )
    return "Write all natural language fields in English."


def build_review_suggestion_messages(
    pr_info, diff_context, risk_result, output_language: str = "en"
) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages for review suggestion generation.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        risk_result: RiskAnalysisResult object.
        output_language: "en" or "zh".

    Returns:
        List of message dicts with "role" and "content" keys.
    """
    system_prompt = _SYSTEM_PROMPT + "\n" + _language_instruction(output_language)

    warning_text = ""
    if diff_context.warnings:
        warning_text = "Diff context warnings: " + "; ".join(diff_context.warnings) + "\n"

    risk_items_text = json.dumps(
        [
            {
                "risk_type": ri.risk_type,
                "severity": ri.severity,
                "file_path": ri.file_path,
                "evidence": ri.evidence,
                "explanation": ri.explanation,
                "impact": ri.impact,
                "confidence": ri.confidence,
            }
            for ri in risk_result.risk_items
        ],
        ensure_ascii=False,
    )
    risk_limitations_text = json.dumps(risk_result.limitations, ensure_ascii=False)

    user_content = (
        f"PR Title: {pr_info.title}\n"
        f"PR Body: {pr_info.body or '(empty)'}\n"
        f"Author: {pr_info.author}\n"
        f"State: {pr_info.state}\n"
        f"Additions: {pr_info.additions}\n"
        f"Deletions: {pr_info.deletions}\n"
        f"Changed Files: {pr_info.changed_files}\n"
        f"{warning_text}"
        f"Overall Risk Level: {risk_result.overall_risk_level}\n"
        f"Risk Items:\n{risk_items_text}\n"
        f"Risk Limitations: {risk_limitations_text}\n"
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

_UNWRAP_KEYS = ["result", "data", "suggestion_result"]

_SUGGESTION_REQUIRED = [
    "title", "priority", "file_path", "problem",
    "evidence", "suggestion", "copy_text",
]

_ALLOWED_PRIORITIES = frozenset({"high", "medium", "low"})


def parse_review_suggestions_response(content: str) -> ReviewSuggestionResult:
    """Parse model JSON output into ReviewSuggestionResult.

    Args:
        content: Raw model output string.

    Returns:
        ReviewSuggestionResult with parsed suggestions.

    Raises:
        ReviewSuggestionParseError: If parsing fails or required fields are missing.
    """
    if not content or not content.strip():
        raise ReviewSuggestionParseError("Model returned empty content.")

    text = content.strip()

    match = _FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ReviewSuggestionParseError(f"Failed to parse JSON: {e}") from e

    if not isinstance(data, dict):
        raise ReviewSuggestionParseError(f"Expected JSON object, got {type(data).__name__}")

    for key in _UNWRAP_KEYS:
        if key in data and isinstance(data[key], dict):
            data = data[key]
            break

    raw_items = data.get("suggestions", [])
    if not isinstance(raw_items, list):
        raise ReviewSuggestionParseError(
            f'"suggestions" must be a list, got {type(raw_items).__name__}'
        )

    suggestions = [_parse_suggestion(item) for item in raw_items]
    limitations = _normalize_suggestion_limitations(data.get("limitations", []))

    return ReviewSuggestionResult(
        suggestions=suggestions,
        limitations=limitations,
        raw_response=content,
    )


def _parse_suggestion(item: dict) -> ReviewSuggestion:
    if not isinstance(item, dict):
        raise ReviewSuggestionParseError(
            f"Expected dict for suggestion item, got {type(item).__name__}"
        )

    for field in _SUGGESTION_REQUIRED:
        val = item.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise ReviewSuggestionParseError(
                f'Missing required field "{field}" in suggestion item'
            )

    priority = str(item.get("priority", "medium")).strip()
    if priority not in _ALLOWED_PRIORITIES:
        priority = "medium"

    need_human_check = _suggestion_to_bool(item.get("need_human_check", True))

    return ReviewSuggestion(
        title=str(item.get("title", "")).strip(),
        priority=priority,
        file_path=str(item.get("file_path", "")).strip(),
        problem=str(item.get("problem", "")).strip(),
        evidence=str(item.get("evidence", "")).strip(),
        impact=str(item.get("impact", "") or "").strip(),
        suggestion=str(item.get("suggestion", "")).strip(),
        copy_text=str(item.get("copy_text", "")).strip(),
        source_risk_type=str(item.get("source_risk_type", "")).strip(),
        need_human_check=need_human_check,
    )


def _normalize_suggestion_limitations(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [stripped]
    raise ReviewSuggestionParseError(
        f'"limitations" must be a list or string, got {type(value).__name__}'
    )


def _suggestion_to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "no", "0", "none", "")
    return bool(value)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def _no_risk_limitation(lang: str) -> str:
    if lang == "zh":
        return "未生成 Review 建议，因为没有可转化为建议的具体风险项。"
    return "No review suggestions were generated because no risk items were provided."


def generate_review_suggestions(
    pr_info, diff_context, risk_result, llm_config: LLMConfig,
    output_language: str = "en",
) -> ReviewSuggestionResult:
    """Generate structured review suggestions from risk analysis results.

    If risk_result has no risk items, returns an empty result without
    calling the LLM.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        risk_result: RiskAnalysisResult object.
        llm_config: LLMConfig for the model call.
        output_language: "en" or "zh".

    Returns:
        ReviewSuggestionResult with parsed suggestions.

    Raises:
        ReviewSuggestionError / ReviewSuggestionParseError: On parse failures.
        LLMClientError / subclasses: On API failures (passed through).
    """
    if not risk_result.risk_items:
        return ReviewSuggestionResult(
            suggestions=[],
            limitations=[_no_risk_limitation(output_language)],
            raw_response="",
        )

    messages = build_review_suggestion_messages(
        pr_info, diff_context, risk_result, output_language=output_language
    )
    response = chat_completion(messages, llm_config)
    return parse_review_suggestions_response(response.content)
