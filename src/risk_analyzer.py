"""PR risk code identification via LLM."""

import json
import re
from dataclasses import dataclass
from typing import Any

from src.llm_client import LLMConfig, LLMResponseError, chat_completion


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

_FENCE_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are a Pull Request risk identification assistant. Only use the provided PR \
information and diff context to identify potential risks. Do not supplement \
with knowledge outside the provided context. Do not judge whether the PR \
should be merged. Do not force risk generation — if no clear risks, return \
empty risk_items. Every risk must contain evidence. Annotate confidence and \
need_human_check for each item.

Return only valid JSON. Do not return empty content.
Do not include markdown fences (```).
Do not include explanations before or after the JSON.
Do not use comments inside JSON.
Use double quotes for all JSON keys and string values.
Use true or false for boolean values. Do not use None, is, 否, Yes, No as booleans.
If no obvious risks are found, return:
{"overall_risk_level":"low","risk_items":[],"limitations":["No obvious risks were found from the provided diff."]}

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


def _language_instruction(lang: str) -> str:
    if lang == "zh":
        return (
            "Write explanation, impact, suggestion, evidence, and limitations in "
            "Simplified Chinese when possible. Keep risk_type, severity, confidence, "
            "file_path, code identifiers, and schema keys unchanged. Natural language "
            "must use Chinese but JSON keys, enum values, and booleans must remain "
            "valid JSON."
        )
    return "Write all natural language fields in English. The response must remain valid JSON."


def build_risk_messages(pr_info, diff_context, output_language: str = "en") -> list[dict[str, str]]:
    """Build OpenAI-compatible messages for risk analysis.

    Args:
        pr_info: PRInfo object from github_client.
        diff_context: DiffContext object from diff_processor.
        output_language: "en" or "zh".

    Returns:
        List of message dicts with "role" and "content" keys.
    """
    system_prompt = _SYSTEM_PROMPT + "\n" + _language_instruction(output_language)

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
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Fallback builders
# ---------------------------------------------------------------------------


def _build_risk_fallback(
    raw_response: str = "",
    output_language: str = "en",
    reason: str = "model_output_invalid",
) -> RiskAnalysisResult:
    if reason == "empty_content":
        if output_language == "zh":
            limitations = [
                "模型在风险分析阶段返回了空内容。",
                "本次未生成具体风险项。",
                "分析仅基于 PR diff，可能遗漏仓库级上下文。",
                "请仍然进行人工审查。",
            ]
        else:
            limitations = [
                "Model returned empty content during risk analysis.",
                "No risk items were generated.",
                "Analysis is based only on PR diff and may miss repository-level context.",
                "Please review the PR manually.",
            ]
    else:
        if output_language == "zh":
            limitations = [
                "风险分析结果未能解析为合法 JSON。",
                "本次未从模型输出中生成具体风险项。",
                "分析仅基于 PR diff，可能遗漏仓库级上下文。",
                "请仍然进行人工审查。",
            ]
        else:
            limitations = [
                "Risk analysis could not be parsed into valid JSON.",
                "No risk items were generated from the model output.",
                "Analysis is based only on PR diff and may miss repository-level context.",
                "Please review the PR manually.",
            ]

    return RiskAnalysisResult(
        overall_risk_level="low",
        risk_items=[],
        limitations=limitations,
        raw_response=raw_response,
    )


def _is_empty_content_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("empty content" in msg or "returned empty content" in msg)


def _build_retry_instruction(output_language: str, parse_error: str) -> str:
    if output_language == "zh":
        return (
            "上一次输出无法解析为合法 JSON。"
            "请重新输出，并且只输出一个 JSON 对象，不要输出 markdown，不要输出解释文字。"
            "必须使用以下顶层字段: "
            '{"overall_risk_level":"low","risk_items":[],"limitations":[]}。'
            "如果没有发现明显风险，请返回: "
            '{"overall_risk_level":"low","risk_items":[],'
            '"limitations":["未从提供的 diff 中发现明显风险。"]}'
        )
    return (
        "The previous output could not be parsed as valid JSON. "
        "Return only one JSON object. Do not include markdown fences or extra explanation. "
        "Use exactly these top-level fields: "
        '{"overall_risk_level":"low","risk_items":[],"limitations":[]}. '
        "If no obvious risk is found, return: "
        '{"overall_risk_level":"low","risk_items":[],'
        '"limitations":["No obvious risks were found from the provided diff."]}'
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_risk_response(
    content: str,
    allow_empty_fallback: bool = False,
    output_language: str = "en",
) -> RiskAnalysisResult:
    """Parse model JSON output into RiskAnalysisResult.

    Args:
        content: Raw model output string.
        allow_empty_fallback: If True, return fallback for empty content instead of raising.
        output_language: "en" or "zh" for fallback messages.

    Returns:
        RiskAnalysisResult with parsed fields.

    Raises:
        RiskResponseParseError: If parsing fails or required fields are missing
            (and allow_empty_fallback is False or content is not empty).
    """
    if not content or not content.strip():
        if allow_empty_fallback:
            return _build_risk_fallback(content, output_language=output_language, reason="empty_content")
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
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("false", "no", "0", "none", "")
    return bool(value)


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def analyze_pr_risks(pr_info, diff_context, llm_config: LLMConfig,
                     output_language: str = "en") -> RiskAnalysisResult:
    """Analyze PR diff for potential risks using the LLM.

    Falls back gracefully on empty content or invalid JSON: retries once,
    then returns a low-risk fallback result.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        llm_config: LLMConfig for the model call.
        output_language: "en" or "zh".

    Returns:
        RiskAnalysisResult with parsed risk items or fallback.

    Raises:
        LLMClientError / subclasses: On auth, rate-limit, or network failures
            (not on parse or empty-content failures).
    """
    messages = build_risk_messages(pr_info, diff_context, output_language=output_language)

    def _first_try():
        try:
            response = chat_completion(messages, llm_config)
        except LLMResponseError as exc:
            if _is_empty_content_error(exc):
                return _build_risk_fallback("", output_language=output_language, reason="empty_content")
            raise
        if not response.content or not response.content.strip():
            return _retry("empty_content", "empty_content")
        try:
            return parse_risk_response(
                response.content,
                allow_empty_fallback=True,
                output_language=output_language,
            )
        except RiskResponseParseError as e:
            return _retry(response.content, str(e))

    def _retry(prev_content: str, reason: str):
        instruction = _build_retry_instruction(output_language, reason)
        retry_messages = messages + [{"role": "user", "content": instruction}]
        try:
            retry_response = chat_completion(retry_messages, llm_config)
        except LLMResponseError as exc:
            if _is_empty_content_error(exc):
                return _build_risk_fallback(prev_content, output_language=output_language, reason="empty_content")
            raise
        if not retry_response.content or not retry_response.content.strip():
            return _build_risk_fallback(prev_content, output_language=output_language, reason="empty_content")
        try:
            return parse_risk_response(
                retry_response.content,
                allow_empty_fallback=True,
                output_language=output_language,
            )
        except RiskResponseParseError:
            return _build_risk_fallback(retry_response.content, output_language=output_language, reason="model_output_invalid")

    return _first_try()
