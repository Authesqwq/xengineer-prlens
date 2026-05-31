"""Structured Review suggestion generation from risk analysis results."""

import json
import re
from dataclasses import dataclass

from src.llm_client import LLMClientError, LLMConfig, chat_completion


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
You are a Pull Request review suggestion generator. Use provided risk items \
to create structured suggestions. Do not force suggestions — return empty \
if no risks. Every suggestion must have evidence and an actionable suggestion.
copy_text must be suitable as a PR review comment draft (max 200 chars).
Return only valid JSON, no markdown fences. Use keys: suggestions, limitations.
priority: high|medium|low. Max 3 suggestions. Keep titles under 60 chars.

Format (compact):
{"suggestions":[{"title":"T","priority":"medium","file_path":"f.py","problem":"P","evidence":"E","impact":"I","suggestion":"S","copy_text":"C","source_risk_type":"logic","need_human_check":true}],"limitations":[]}"""


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


def _build_fallback_suggestions(risk_items, output_language: str = "en") -> list:
    """Build deterministic fallback suggestions from risk items.

    Each risk item generates one fallback suggestion with a human-review notice.
    Maximum 3 suggestions. All marked with source_risk_type='fallback'.
    """
    zh = output_language == "zh"
    fallback_suggestions = []
    for ri in risk_items[:3]:
        title = (
            f"人工复核: {ri.risk_type} 风险于 {ri.file_path}"
            if zh else
            f"Manual review: {ri.risk_type} risk in {ri.file_path}"
        )
        copy_text = (
            f"建议人工复核该变更：当前风险项指出 {ri.evidence}，可能影响 {ri.risk_type}。"
            f"建议补充边界处理、异常处理或测试用例后再合并。"
            if zh else
            f"Please manually review: the risk is related to {ri.evidence} "
            f"and may affect {ri.risk_type}. Consider adding validation, "
            f"error handling, or tests before merging."
        )
        fallback_suggestions.append(ReviewSuggestion(
            title=title,
            priority=ri.severity if ri.severity in ("high", "medium", "low") else "medium",
            file_path=ri.file_path,
            problem=ri.explanation or ri.evidence,
            evidence=ri.evidence,
            impact=ri.impact or "",
            suggestion=ri.suggestion or ("" if zh else ""),
            copy_text=copy_text,
            source_risk_type="fallback",
            need_human_check=True,
        ))
    return fallback_suggestions


def generate_review_suggestions(
    pr_info, diff_context, risk_result, llm_config: LLMConfig,
    output_language: str = "en",
) -> ReviewSuggestionResult:
    """Generate structured review suggestions from risk analysis results.

    If risk_result has no risk items, returns empty without calling LLM.
    On empty content or JSON parse failure, retries once with compact prompt.
    If retry also fails, builds deterministic fallback suggestions from risk items.

    Args:
        pr_info: PRInfo object.
        diff_context: DiffContext object.
        risk_result: RiskAnalysisResult object with risk_items.
        llm_config: LLMConfig for the model call.
        output_language: "en" or "zh".

    Returns:
        ReviewSuggestionResult — always returns a result on parse error.
    """
    if not risk_result.risk_items:
        return ReviewSuggestionResult(
            suggestions=[],
            limitations=[_no_risk_limitation(output_language)],
            raw_response="",
        )

    zh = output_language == "zh"

    def _try_generate(msgs):
        try:
            resp = chat_completion(msgs, llm_config)
            if not resp.content or not resp.content.strip():
                return None
            return parse_review_suggestions_response(resp.content)
        except (LLMClientError, ReviewSuggestionParseError):
            return None

    messages = build_review_suggestion_messages(
        pr_info, diff_context, risk_result, output_language=output_language
    )
    result = _try_generate(messages)
    if result is not None:
        return result

    # Retry with compact instruction
    retry_msg = (
        "上一次输出无法解析。请只返回一个紧凑 JSON 对象，最多 3 条 suggestions，"
        "每条 copy_text 不超过 200 字符。不要使用 markdown。"
        if zh else
        "Previous output could not be parsed. Return only one compact JSON object, "
        "max 3 suggestions, copy_text max 200 chars. No markdown."
    )
    retry_msgs = messages + [{"role": "user", "content": retry_msg}]
    try:
        retry_resp = chat_completion(retry_msgs, llm_config)
        if retry_resp.content and retry_resp.content.strip():
            try:
                return parse_review_suggestions_response(retry_resp.content)
            except ReviewSuggestionParseError:
                pass
    except LLMClientError:
        pass

    # Deterministic fallback
    fallback = _build_fallback_suggestions(risk_result.risk_items, output_language)
    lim = (
        ["Review Suggestions 使用降级规则生成，需人工复核。"]
        if zh else
        ["Review suggestions were generated by deterministic fallback. Manual review required."]
    )
    return ReviewSuggestionResult(
        suggestions=fallback,
        limitations=lim,
        raw_response="",
    )
