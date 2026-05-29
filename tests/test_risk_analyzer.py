"""Tests for PR risk analyzer (all LLM calls mocked)."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from src.llm_client import LLMConfig, LLMResponse
from src.risk_analyzer import (
    RiskAnalysisResult,
    RiskItem,
    RiskResponseParseError,
    analyze_pr_risks,
    build_risk_messages,
    parse_risk_response,
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


def _make_config():
    return LLMConfig(api_key="sk-t", model="m", base_url="https://a.example.com/v1")


def _make_response(content):
    return LLMResponse(content=content, model="m", usage={}, raw_response={})


def _sample_risk_json(**overrides):
    data = {
        "overall_risk_level": "medium",
        "risk_items": [
            {
                "risk_type": "logic",
                "severity": "medium",
                "file_path": "src/login.py",
                "evidence": "Removed null check at line 12",
                "explanation": "Null check removed without alternative validation",
                "impact": "Null username may crash the login flow",
                "suggestion": "Add explicit None check before using username",
                "confidence": "medium",
                "need_human_check": False,
            }
        ],
        "limitations": ["Analysis limited to diff context only"],
    }
    data.update(overrides)
    return data


def _sample_empty_risk_json():
    return {
        "overall_risk_level": "low",
        "risk_items": [],
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# build_risk_messages
# ---------------------------------------------------------------------------


class TestBuildRiskMessages:
    def test_returns_two_messages(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"

    def test_system_contains_input_only_constraint(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        s = msgs[0]["content"].lower()
        assert "only use the provided" in s

    def test_system_contains_no_force_risk(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        s = msgs[0]["content"].lower()
        assert "do not force risk" in s

    def test_system_contains_risk_types(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        s = msgs[0]["content"]
        for rt in ["logic", "boundary", "error_handling", "testing",
                    "security", "performance", "compatibility", "maintainability"]:
            assert rt in s

    def test_system_contains_evidence_requirement(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        s = msgs[0]["content"].lower()
        assert "evidence" in s

    def test_user_contains_pr_title(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        assert "Add login validation" in msgs[1]["content"]

    def test_user_contains_diff_context(self):
        msgs = build_risk_messages(FakePRInfo(), FakeDiffContext())
        assert "src/login.py" in msgs[1]["content"]

    def test_user_contains_diff_warnings(self):
        dc = FakeDiffContext(warnings=["File truncated"])
        msgs = build_risk_messages(FakePRInfo(), dc)
        assert "File truncated" in msgs[1]["content"]

    def test_user_no_warning_section_when_empty(self):
        dc = FakeDiffContext(warnings=[])
        msgs = build_risk_messages(FakePRInfo(), dc)
        assert "Diff context warnings" not in msgs[1]["content"]


# ---------------------------------------------------------------------------
# parse_risk_response
# ---------------------------------------------------------------------------


class TestParseRiskResponse:
    def test_parses_standard_json(self):
        import json
        data = _sample_risk_json()
        result = parse_risk_response(json.dumps(data))
        assert result.overall_risk_level == "medium"
        assert len(result.risk_items) == 1
        assert result.risk_items[0].risk_type == "logic"
        assert result.raw_response == json.dumps(data)

    def test_parses_fenced_json(self):
        import json
        data = _sample_risk_json()
        content = "```json\n" + json.dumps(data) + "\n```"
        result = parse_risk_response(content)
        assert result.overall_risk_level == "medium"

    def test_unwraps_result_nesting(self):
        import json
        data = _sample_risk_json()
        content = json.dumps({"result": data})
        result = parse_risk_response(content)
        assert result.overall_risk_level == "medium"

    def test_overall_risk_level_missing_defaults_low(self):
        import json
        data = _sample_risk_json()
        del data["overall_risk_level"]
        result = parse_risk_response(json.dumps(data))
        assert result.overall_risk_level == "low"

    def test_overall_risk_level_invalid_defaults_low(self):
        import json
        data = _sample_risk_json(overall_risk_level="critical")
        result = parse_risk_response(json.dumps(data))
        assert result.overall_risk_level == "low"

    def test_risk_items_missing_defaults_empty(self):
        import json
        data = _sample_risk_json()
        del data["risk_items"]
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items == []

    def test_limitations_missing_defaults_empty(self):
        import json
        data = _sample_risk_json()
        del data["limitations"]
        result = parse_risk_response(json.dumps(data))
        assert result.limitations == []

    def test_limitations_string_becomes_list(self):
        import json
        data = _sample_risk_json(limitations="Only partial context")
        result = parse_risk_response(json.dumps(data))
        assert result.limitations == ["Only partial context"]

    def test_limitations_none_becomes_empty(self):
        import json
        data = _sample_risk_json(limitations=None)
        result = parse_risk_response(json.dumps(data))
        assert result.limitations == []

    def test_risk_items_not_list_raises(self):
        import json
        data = _sample_risk_json(risk_items="not a list")
        with pytest.raises(RiskResponseParseError, match="risk_items"):
            parse_risk_response(json.dumps(data))

    def test_non_json_raises(self):
        with pytest.raises(RiskResponseParseError):
            parse_risk_response("not json")

    def test_empty_string_raises(self):
        with pytest.raises(RiskResponseParseError):
            parse_risk_response("")

    def test_empty_risk_response_parses(self):
        import json
        result = parse_risk_response(json.dumps(_sample_empty_risk_json()))
        assert result.risk_items == []
        assert result.overall_risk_level == "low"

    def test_evidence_missing_raises(self):
        import json
        data = _sample_risk_json()
        del data["risk_items"][0]["evidence"]
        with pytest.raises(RiskResponseParseError, match="evidence"):
            parse_risk_response(json.dumps(data))

    def test_severity_invalid_defaults_medium(self):
        import json
        data = _sample_risk_json()
        data["risk_items"][0]["severity"] = "critical"
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items[0].severity == "medium"

    def test_confidence_invalid_defaults_medium(self):
        import json
        data = _sample_risk_json()
        data["risk_items"][0]["confidence"] = "very_high"
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items[0].confidence == "medium"

    def test_risk_type_unknown_sets_need_human_check(self):
        import json
        data = _sample_risk_json()
        data["risk_items"][0]["risk_type"] = "unknown_type"
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items[0].risk_type == "unknown_type"
        assert result.risk_items[0].need_human_check is True

    def test_need_human_check_defaults_true(self):
        import json
        data = _sample_risk_json()
        del data["risk_items"][0]["need_human_check"]
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items[0].need_human_check is True

    def test_impact_missing_defaults_empty(self):
        import json
        data = _sample_risk_json()
        del data["risk_items"][0]["impact"]
        result = parse_risk_response(json.dumps(data))
        assert result.risk_items[0].impact == ""

    def test_all_required_fields_present(self):
        import json
        data = _sample_risk_json()
        result = parse_risk_response(json.dumps(data))
        ri = result.risk_items[0]
        assert ri.risk_type == "logic"
        assert ri.severity == "medium"
        assert ri.file_path == "src/login.py"
        assert "null check" in ri.evidence
        assert ri.explanation
        assert ri.suggestion


# ---------------------------------------------------------------------------
# analyze_pr_risks
# ---------------------------------------------------------------------------


class TestAnalyzePRRisks:
    def test_calls_chat_completion(self):
        import json
        resp = _make_response(json.dumps(_sample_risk_json()))
        with patch("src.risk_analyzer.chat_completion", return_value=resp) as mock_cc:
            analyze_pr_risks(FakePRInfo(), FakeDiffContext(), _make_config())
            assert mock_cc.called

    def test_returns_risk_analysis_result(self):
        import json
        resp = _make_response(json.dumps(_sample_risk_json()))
        with patch("src.risk_analyzer.chat_completion", return_value=resp):
            result = analyze_pr_risks(FakePRInfo(), FakeDiffContext(), _make_config())
            assert isinstance(result, RiskAnalysisResult)
            assert result.overall_risk_level == "medium"

    def test_passes_messages_and_config(self):
        import json
        resp = _make_response(json.dumps(_sample_risk_json()))
        cfg = _make_config()
        with patch("src.risk_analyzer.chat_completion", return_value=resp) as mock_cc:
            analyze_pr_risks(FakePRInfo(), FakeDiffContext(), cfg)
            assert mock_cc.call_args[0][1] == cfg
            messages = mock_cc.call_args[0][0]
            assert len(messages) == 2
