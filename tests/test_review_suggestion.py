"""Tests for review suggestion generator (all LLM calls mocked)."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from src.llm_client import LLMConfig, LLMResponse
from src.review_suggestion import (
    ReviewSuggestionError,
    ReviewSuggestionParseError,
    ReviewSuggestionResult,
    build_review_suggestion_messages,
    generate_review_suggestions,
    parse_review_suggestions_response,
)


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


@dataclass
class FakePRInfo:
    title: str = "Add login validation"
    body: str = "Validate input on login form"
    author: str = "dev1"
    state: str = "closed"
    additions: int = 42
    deletions: int = 10
    changed_files: int = 3


@dataclass
class FakeDiffContext:
    content: str = "## File: src/login.py\n\n```diff\n+if not username:\n+    return\n```\n"
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


@dataclass
class FakeRiskItem:
    risk_type: str = "testing"
    severity: str = "medium"
    file_path: str = "src/login.py"
    evidence: str = "No test file added"
    explanation: str = "Missing test coverage"
    impact: str = "May break silently"
    suggestion: str = "Add a unit test"
    confidence: str = "medium"
    need_human_check: bool = True


@dataclass
class FakeRiskResult:
    overall_risk_level: str = "medium"
    risk_items: list = None
    limitations: list = None

    def __post_init__(self):
        if self.risk_items is None:
            self.risk_items = [FakeRiskItem()]
        if self.limitations is None:
            self.limitations = ["Limited context"]


def _make_config():
    return LLMConfig(api_key="sk", model="m", base_url="https://x.com/v1")


def _make_response(content):
    return LLMResponse(content=content, model="m", usage={}, raw_response={})


def _sample_suggestion_json(**overrides):
    data = {
        "suggestions": [
            {
                "title": "Add test for login validation",
                "priority": "medium",
                "file_path": "src/login.py",
                "problem": "No test covers the new validation logic.",
                "evidence": "The diff adds logic in login.py but no test file was modified.",
                "impact": "Future changes may break validation silently.",
                "suggestion": "Add a unit test covering empty username input.",
                "copy_text": "Could you add a unit test for the empty username case?",
                "source_risk_type": "testing",
                "need_human_check": True,
            }
        ],
        "limitations": [],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# build_review_suggestion_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_returns_two_messages(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_contains_input_only_constraint(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        s = msgs[0]["content"].lower()
        assert "use provided risk items" in s

    def test_system_contains_no_force_suggestions(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        s = msgs[0]["content"].lower()
        assert "do not force" in s

    def test_system_contains_copy_text(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert "copy_text" in msgs[0]["content"].lower()

    def test_user_contains_pr_title(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert "Add login validation" in msgs[1]["content"]

    def test_user_contains_diff_context(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert "src/login.py" in msgs[1]["content"]

    def test_user_contains_risk_items(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert "testing" in msgs[1]["content"]

    def test_user_contains_risk_limitations(self):
        msgs = build_review_suggestion_messages(FakePRInfo(), FakeDiffContext(), FakeRiskResult())
        assert "Limited context" in msgs[1]["content"]

    def test_zh_language_in_system_prompt(self):
        msgs = build_review_suggestion_messages(
            FakePRInfo(), FakeDiffContext(), FakeRiskResult(), output_language="zh"
        )
        system = msgs[0]["content"]
        assert "Simplified Chinese" in system

    def test_en_language_default(self):
        msgs = build_review_suggestion_messages(
            FakePRInfo(), FakeDiffContext(), FakeRiskResult()
        )
        system = msgs[0]["content"]
        assert "Simplified Chinese" not in system
        assert "English" in system


# ---------------------------------------------------------------------------
# parse_review_suggestions_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    def test_parses_standard_json(self):
        import json
        data = _sample_suggestion_json()
        result = parse_review_suggestions_response(json.dumps(data))
        assert len(result.suggestions) == 1
        assert result.suggestions[0].title == "Add test for login validation"

    def test_parses_fenced_json(self):
        import json
        data = _sample_suggestion_json()
        content = "```json\n" + json.dumps(data) + "\n```"
        result = parse_review_suggestions_response(content)
        assert len(result.suggestions) == 1

    def test_unwraps_result_nesting(self):
        import json
        data = _sample_suggestion_json()
        content = json.dumps({"result": data})
        result = parse_review_suggestions_response(content)
        assert len(result.suggestions) == 1

    def test_suggestions_missing_defaults_empty(self):
        import json
        data = _sample_suggestion_json(suggestions=None)
        del data["suggestions"]
        result = parse_review_suggestions_response(json.dumps(data))
        assert result.suggestions == []

    def test_limitations_missing_defaults_empty(self):
        import json
        data = _sample_suggestion_json()
        del data["limitations"]
        result = parse_review_suggestions_response(json.dumps(data))
        assert result.limitations == []

    def test_limitations_string_becomes_list(self):
        import json
        data = _sample_suggestion_json(limitations="Partial context only")
        result = parse_review_suggestions_response(json.dumps(data))
        assert result.limitations == ["Partial context only"]

    def test_suggestions_not_list_raises(self):
        import json
        data = _sample_suggestion_json(suggestions="not a list")
        with pytest.raises(ReviewSuggestionParseError, match="suggestions"):
            parse_review_suggestions_response(json.dumps(data))

    def test_non_json_raises(self):
        with pytest.raises(ReviewSuggestionParseError):
            parse_review_suggestions_response("not json")

    def test_empty_string_raises(self):
        with pytest.raises(ReviewSuggestionParseError):
            parse_review_suggestions_response("")

    def test_empty_suggestions_parses(self):
        import json
        data = {"suggestions": [], "limitations": []}
        result = parse_review_suggestions_response(json.dumps(data))
        assert result.suggestions == []

    def test_missing_evidence_raises(self):
        import json
        data = _sample_suggestion_json()
        del data["suggestions"][0]["evidence"]
        with pytest.raises(ReviewSuggestionParseError, match="evidence"):
            parse_review_suggestions_response(json.dumps(data))

    def test_missing_copy_text_raises(self):
        import json
        data = _sample_suggestion_json()
        del data["suggestions"][0]["copy_text"]
        with pytest.raises(ReviewSuggestionParseError, match="copy_text"):
            parse_review_suggestions_response(json.dumps(data))

    def test_priority_invalid_defaults_medium(self):
        import json
        data = _sample_suggestion_json()
        data["suggestions"][0]["priority"] = "critical"
        result = parse_review_suggestions_response(json.dumps(data))
        assert result.suggestions[0].priority == "medium"

    def test_optional_fields_default(self):
        import json
        data = _sample_suggestion_json()
        del data["suggestions"][0]["impact"]
        del data["suggestions"][0]["source_risk_type"]
        del data["suggestions"][0]["need_human_check"]
        result = parse_review_suggestions_response(json.dumps(data))
        s = result.suggestions[0]
        assert s.impact == ""
        assert s.source_risk_type == ""
        assert s.need_human_check is True

    def test_all_required_fields_parsed(self):
        import json
        data = _sample_suggestion_json()
        result = parse_review_suggestions_response(json.dumps(data))
        s = result.suggestions[0]
        assert s.title
        assert s.problem
        assert s.evidence
        assert s.suggestion
        assert s.copy_text
        assert s.file_path


# ---------------------------------------------------------------------------
# generate_review_suggestions
# ---------------------------------------------------------------------------


class TestGenerateSuggestions:
    def test_calls_chat_completion_when_risks_present(self):
        import json
        resp = _make_response(json.dumps(_sample_suggestion_json()))
        with patch("src.review_suggestion.chat_completion", return_value=resp) as mock_cc:
            generate_review_suggestions(
                FakePRInfo(), FakeDiffContext(), FakeRiskResult(), _make_config()
            )
            assert mock_cc.called

    def test_returns_review_suggestion_result(self):
        import json
        resp = _make_response(json.dumps(_sample_suggestion_json()))
        with patch("src.review_suggestion.chat_completion", return_value=resp):
            result = generate_review_suggestions(
                FakePRInfo(), FakeDiffContext(), FakeRiskResult(), _make_config()
            )
            assert isinstance(result, ReviewSuggestionResult)
            assert len(result.suggestions) == 1

    def test_skips_llm_when_no_risk_items(self):
        with patch("src.review_suggestion.chat_completion") as mock_cc:
            result = generate_review_suggestions(
                FakePRInfo(),
                FakeDiffContext(),
                FakeRiskResult(risk_items=[]),
                _make_config(),
            )
            assert not mock_cc.called
            assert result.suggestions == []
            assert "no risk items" in result.limitations[0].lower()

    def test_no_risk_items_raw_response_empty(self):
        result = generate_review_suggestions(
            FakePRInfo(),
            FakeDiffContext(),
            FakeRiskResult(risk_items=[]),
            _make_config(),
        )
        assert result.raw_response == ""

    def test_no_risk_items_chinese_limitation(self):
        result = generate_review_suggestions(
            FakePRInfo(),
            FakeDiffContext(),
            FakeRiskResult(risk_items=[]),
            _make_config(),
            output_language="zh",
        )
        assert "风险" in result.limitations[0]

    def test_no_risk_items_english_limitation(self):
        result = generate_review_suggestions(
            FakePRInfo(),
            FakeDiffContext(),
            FakeRiskResult(risk_items=[]),
            _make_config(),
            output_language="en",
        )
        assert "No review suggestions" in result.limitations[0]
