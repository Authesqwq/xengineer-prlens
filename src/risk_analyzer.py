"""PR risk code identification via LLM."""

import json
import re
from dataclasses import dataclass
from typing import Any

from src.llm_client import LLMConfig, chat_completion


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RiskItem:
    risk_type: str
    severity: str
    file_path: str
    evidence: str
    explanation: str
    impact: str
    suggestion: str
    confidence: str
    need_human_check: bool


@dataclass
class RiskAnalysisResult:
    overall_risk_level: str
    risk_items: list[RiskItem]
    limitations: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RiskAnalyzerError(RuntimeError):
    pass


class RiskResponseParseError(RiskAnalyzerError):
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_RISK_TYPES = frozenset({
    "logic", "boundary", "error_handling", "testing",
    "security", "performance", "compatibility", "maintainability",
})

_ALLOWED_LEVELS = frozenset({"low", "medium", "high"})

_RISK_REQUIRED_FIELDS = [
    "risk_type", "severity", "file_path", "evidence", "explanation", "suggestion",
]

_UNWRAP_KEYS = ["result", "data", "risk_result"]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a Pull Request risk identification assistant. Only use the provided PR \
information and diff context to identify potential risks. Do not supplement \
with knowledge outside the provided context. Do not judge whether the PR \
should be merged. Do not force risk generation — if no clear risks, return \
empty risk_items. Every risk must contain evidence. Annotate confidence and \
need_human_check for each item. Return only valid JSON.

Use exactly these top-level keys: overall_risk_level, risk_items, limitations.

Allowed risk_type values: logic, boundary, error_handling, testing, security, \
performance, compatibility, maintainability.
severity and confidence must be one of: low, medium, high.

Format:
{
  "overall_risk_level": "low",
  "risk_items": [
    {
      "risk_type": "logic",
      "severity": "medium",
      "file_path": "src/example.py",
      "evidence": "...",
      "explanation": "...",
      "impact": "...",
      "suggestion": "...",
      "confidence": "medium",
      "need_human_check": true
    }
  ],
  "limitations": []
}"""


def build_risk_messages(pr_info, diff_context) -> list[dict[str, str]]:
    """Build OpenAI-compatible messages for risk analysis.

    Args:
        pr_info: PRInfo object from github_client.
        diff_context: DiffContext object from diff_processor.

    Returns:
        List of message dicts with "role" and "content" keys.
    """
    warning_text = ""
    if diff_context.warnings:
        warning_text = "Diff context warnings: " + "; ".join(diff_context.warnings) + "\n"

    user_content = (
        f"PR Title: {pr_info.title}\n"
        f"PR Body: {pr_info.body or '(empty)'}\n"
        f"Author: {pr_info.author}\n"
        f"State: {pr_info.state}\n"
        f"Additions: {pr_info.additions}\n"
        f"Deletions: {pr_info.deletions}\n"
        f"Changed Files: {pr_info.changed_files}\n"
        f"{warning_text}"
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


def parse_risk_response(content: str) -> RiskAnalysisResult:
    """Parse model JSON output into RiskAnalysisResult.

    Args:
        content: Raw model output string.

    Returns:
        RiskAnalysisResult with parsed fields.

    Raises:
        RiskResponseParseError: If parsing fails or required fields are missing.
    """
    if not content or not content.strip():
        raise RiskResponseParseError("Model returned empty content.")

    text = content.strip()

    match = _FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RiskResponseParseError(f"Failed to parse JSON: {e}") from e

    if not isinstance(data, dict):
        raise RiskResponseParseError(f"Expected JSON object, got {type(data).__name__}")

    # Unwrap single-level nesting
    for key in _UNWRAP_KEYS:
        if key in data and isinstance(data[key], dict):
            data = data[key]
            break

    overall_risk_level = str(data.get("overall_risk_level", "low") or "low").strip()
    if overall_risk_level not in _ALLOWED_LEVELS:
        overall_risk_level = "low"

    raw_items = data.get("risk_items", [])
    if not isinstance(raw_items, list):
        raise RiskResponseParseError(
            f'"risk_items" must be a list, got {type(raw_items).__name__}'
        )

    risk_items = [_parse_risk_item(item) for item in raw_items]
    limitations = _normalize_limitations(data.get("limitations", []))

    return RiskAnalysisResult(
        overall_risk_level=overall_risk_level,
        risk_items=risk_items,
        limitations=limitations,
        raw_response=content,
    )


def _parse_risk_item(item: dict) -> RiskItem:
    """Parse a single risk item dict into RiskItem, with defaults and validation."""
    if not isinstance(item, dict):
        raise RiskResponseParseError(f"Expected dict for risk item, got {type(item).__name__}")

    for field in _RISK_REQUIRED_FIELDS:
        val = item.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            raise RiskResponseParseError(f'Missing required field "{field}" in risk item')

    risk_type = str(item.get("risk_type", "")).strip()
    need_human_check = _to_bool(item.get("need_human_check", True))
    if risk_type not in _ALLOWED_RISK_TYPES:
        need_human_check = True

    severity = str(item.get("severity", "medium")).strip()
    if severity not in _ALLOWED_LEVELS:
        severity = "medium"

    confidence = str(item.get("confidence", "medium")).strip()
    if confidence not in _ALLOWED_LEVELS:
        confidence = "medium"

    return RiskItem(
        risk_type=risk_type,
        severity=severity,
        file_path=str(item.get("file_path", "")).strip(),
        evidence=str(item.get("evidence", "")).strip(),
        explanation=str(item.get("explanation", "")).strip(),
        impact=str(item.get("impact", "") or "").strip(),
        suggestion=str(item.get("suggestion", "")).strip(),
        confidence=confidence,
        need_human_check=need_human_check,
    )


def _normalize_limitations(value) -> list[str]:
    """Normalize the limitations field to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [stripped]
    raise RiskResponseParseError(
        f'"limitations" must be a list or string, got {type(value).__name__}'
    )


def _to_bool(value) -> bool:
    """Convert a value to bool, treating common falsy JSON patterns."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "no", "0", "none", "")
    return bool(value)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def analyze_pr_risks(pr_info, diff_context, llm_config: LLMConfig) -> RiskAnalysisResult:
    """Analyze PR diff for potential risks using the LLM.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        llm_config: LLMConfig for the model call.

    Returns:
        RiskAnalysisResult with parsed risk items.

    Raises:
        RiskAnalyzerError / RiskResponseParseError: On parse failures.
        LLMClientError / subclasses: On API failures (passed through).
    """
    messages = build_risk_messages(pr_info, diff_context)
    response = chat_completion(messages, llm_config)
    return parse_risk_response(response.content)
