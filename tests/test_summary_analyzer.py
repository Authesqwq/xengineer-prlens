"""Tests for PR summary analyzer (all LLM calls mocked)."""

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from src.llm_client import LLMConfig, LLMResponse
from src.summary_analyzer import (
    SummaryResponseParseError,
    SummaryResult,
    build_summary_messages,
    generate_pr_summary,
    parse_summary_response,
)


# ---------------------------------------------------------------------------
# Fake data helpers
# ---------------------------------------------------------------------------


@dataclass
class FakePRInfo:
    title: str = "Add login validation"
    body: str = "Validate user input on login form"
    author: str = "dev1"
    state: str = "closed"
    additions: int = 42
    deletions: int = 10
    changed_files: int = 3


@dataclass
class FakeDiffContext:
    content: str = "## File: src/login.py\n\n```diff\n+if not username:\n+    raise ValueError\n```\n"


def _make_config():
    return LLMConfig(
        api_key="sk-test", model="test-model",
        base_url="https://api.example.com/v1",
    )


def _make_response(content):
    return LLMResponse(
        content=content, model="test-model",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
        raw_response={"choices": [{"message": {"content": content}}]},
    )


def _sample_summary_json(**overrides):
    data = {
        "summary": "This PR adds input validation to the login form.",
        "main_changes": ["Added validation in src/login.py"],
        "affected_areas": ["Authentication"],
        "uncertainties": [],
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# build_summary_messages
# ---------------------------------------------------------------------------


class TestBuildSummaryMessages:
    def test_returns_two_messages(self):
        msgs = build_summary_messages(FakePRInfo(), FakeDiffContext())
        assert len(msgs) == 2
        roles = [m["role"] for m in msgs]
        assert roles == ["system", "user"]

    def test_system_message_has_constraints(self):
        msgs = build_summary_messages(FakePRInfo(), FakeDiffContext())
        system = msgs[0]["content"]
        assert "code review assistant" in system.lower()
        assert "only use the provided" in system.lower()
        assert "do not supplement" in system.lower()
        assert "uncertainties" in system.lower()
        assert "json" in system.lower()

    def test_user_message_has_pr_title(self):
        msgs = build_summary_messages(FakePRInfo(), FakeDiffContext())
        assert "Add login validation" in msgs[1]["content"]

    def test_user_message_has_diff_context(self):
        msgs = build_summary_messages(FakePRInfo(), FakeDiffContext())
        assert "src/login.py" in msgs[1]["content"]

    def test_user_message_has_pr_fields(self):
        msgs = build_summary_messages(FakePRInfo(), FakeDiffContext())
        user = msgs[1]["content"]
        assert "PR Title:" in user
        assert "PR Body:" in user
        assert "Author:" in user
        assert "State:" in user
        assert "Additions:" in user
        assert "Deletions:" in user
        assert "Changed Files:" in user

    def test_empty_body_shown_as_placeholder(self):
        msgs = build_summary_messages(FakePRInfo(body=""), FakeDiffContext())
        assert "(empty)" in msgs[1]["content"]


# ---------------------------------------------------------------------------
# parse_summary_response
# ---------------------------------------------------------------------------


class TestParseSummaryResponse:
    def test_parses_standard_json(self):
        import json
        data = _sample_summary_json()
        result = parse_summary_response(json.dumps(data))
        assert result.summary == data["summary"]
        assert result.main_changes == data["main_changes"]
        assert result.affected_areas == data["affected_areas"]
        assert result.uncertainties == []
        assert result.raw_response == json.dumps(data)

    def test_parses_fenced_json(self):
        import json
        data = _sample_summary_json()
        content = "```json\n" + json.dumps(data) + "\n```"
        result = parse_summary_response(content)
        assert result.summary == data["summary"]

    def test_parses_fenced_without_json_tag(self):
        import json
        data = _sample_summary_json()
        content = "```\n" + json.dumps(data) + "\n```"
        result = parse_summary_response(content)
        assert result.summary == data["summary"]

    def test_main_changes_missing_defaults_empty_list(self):
        import json
        data = _sample_summary_json()
        del data["main_changes"]
        result = parse_summary_response(json.dumps(data))
        assert result.main_changes == []

    def test_affected_areas_missing_defaults_empty_list(self):
        import json
        data = _sample_summary_json()
        del data["affected_areas"]
        result = parse_summary_response(json.dumps(data))
        assert result.affected_areas == []

    def test_uncertainties_missing_defaults_empty_list(self):
        import json
        data = _sample_summary_json()
        del data["uncertainties"]
        result = parse_summary_response(json.dumps(data))
        assert result.uncertainties == []

    def test_empty_content_raises(self):
        with pytest.raises(SummaryResponseParseError):
            parse_summary_response("")

    def test_whitespace_only_raises(self):
        with pytest.raises(SummaryResponseParseError):
            parse_summary_response("   ")

    def test_non_json_raises(self):
        with pytest.raises(SummaryResponseParseError):
            parse_summary_response("not json at all")

    def test_missing_summary_raises(self):
        import json
        data = _sample_summary_json()
        del data["summary"]
        with pytest.raises(SummaryResponseParseError, match="Available keys"):
            parse_summary_response(json.dumps(data))

    def test_overview_alias_used_when_summary_missing(self):
        import json
        data = _sample_summary_json(overview="Changed login flow")
        del data["summary"]
        result = parse_summary_response(json.dumps(data))
        assert result.summary == "Changed login flow"

    def test_pr_summary_alias_used(self):
        import json
        data = _sample_summary_json(pr_summary="PR adds validation")
        del data["summary"]
        result = parse_summary_response(json.dumps(data))
        assert result.summary == "PR adds validation"

    def test_change_summary_alias_used(self):
        import json
        data = _sample_summary_json(change_summary="Refactored auth module")
        del data["summary"]
        result = parse_summary_response(json.dumps(data))
        assert result.summary == "Refactored auth module"

    def test_priority_order_summary_over_alias(self):
        import json
        data = _sample_summary_json(
            summary="Primary",
            overview="Should not be used",
        )
        result = parse_summary_response(json.dumps(data))
        assert result.summary == "Primary"

    def test_empty_summary_falls_back_to_overview(self):
        import json
        data = _sample_summary_json(summary="  ", overview="Real summary")
        result = parse_summary_response(json.dumps(data))
        assert result.summary == "Real summary"

    def test_alias_value_not_string_raises(self):
        import json
        data = _sample_summary_json(overview=123)
        del data["summary"]
        with pytest.raises(SummaryResponseParseError, match="overview"):
            parse_summary_response(json.dumps(data))

    def test_nested_result_summary_is_unwrapped(self):
        import json
        inner = _sample_summary_json()
        data = {"result": inner}
        result = parse_summary_response(json.dumps(data))
        assert result.summary == inner["summary"]

    def test_no_summary_alias_at_all_raises_with_available_keys(self):
        import json
        data = {"main_changes": [], "other_field": "x"}
        with pytest.raises(SummaryResponseParseError, match="Available keys"):
            parse_summary_response(json.dumps(data))

    def test_uncertainties_string_normalized_to_single_element_list(self):
        import json
        data = _sample_summary_json(uncertainties="Need more context")
        result = parse_summary_response(json.dumps(data))
        assert result.uncertainties == ["Need more context"]

    def test_uncertainties_none_string_becomes_empty_list(self):
        import json
        data = _sample_summary_json(uncertainties="None")
        result = parse_summary_response(json.dumps(data))
        assert result.uncertainties == []

    def test_main_changes_string_normalized_to_list(self):
        import json
        data = _sample_summary_json(main_changes="Updated login logic")
        result = parse_summary_response(json.dumps(data))
        assert result.main_changes == ["Updated login logic"]

    def test_affected_areas_string_normalized_to_list(self):
        import json
        data = _sample_summary_json(affected_areas="Authentication")
        result = parse_summary_response(json.dumps(data))
        assert result.affected_areas == ["Authentication"]

    def test_uncertainties_empty_string_becomes_empty_list(self):
        import json
        data = _sample_summary_json(uncertainties="")
        result = parse_summary_response(json.dumps(data))
        assert result.uncertainties == []

    def test_uncertainties_none_value_becomes_empty_list(self):
        import json
        data = _sample_summary_json(uncertainties=None)
        result = parse_summary_response(json.dumps(data))
        assert result.uncertainties == []

    def test_lists_still_work_normally(self):
        import json
        data = _sample_summary_json(main_changes=["a", "b"], uncertainties=["x"])
        result = parse_summary_response(json.dumps(data))
        assert result.main_changes == ["a", "b"]
        assert result.uncertainties == ["x"]

    def test_list_elements_converted_to_string(self):
        import json
        data = _sample_summary_json(main_changes=[1, 2])
        result = parse_summary_response(json.dumps(data))
        assert result.main_changes == ["1", "2"]

    def test_dict_still_raises(self):
        import json
        data = _sample_summary_json(affected_areas={"x": 1})
        with pytest.raises(SummaryResponseParseError, match="affected_areas"):
            parse_summary_response(json.dumps(data))

    def test_int_still_raises(self):
        import json
        data = _sample_summary_json(uncertainties=123)
        with pytest.raises(SummaryResponseParseError, match="uncertainties"):
            parse_summary_response(json.dumps(data))


# ---------------------------------------------------------------------------
# generate_pr_summary
# ---------------------------------------------------------------------------


class TestGeneratePRSummary:
    def test_calls_chat_completion(self):
        import json
        resp = _make_response(json.dumps(_sample_summary_json()))
        with patch("src.summary_analyzer.chat_completion", return_value=resp) as mock_cc:
            generate_pr_summary(FakePRInfo(), FakeDiffContext(), _make_config())
            assert mock_cc.called

    def test_returns_summary_result(self):
        import json
        data = _sample_summary_json()
        resp = _make_response(json.dumps(data))
        with patch("src.summary_analyzer.chat_completion", return_value=resp):
            result = generate_pr_summary(FakePRInfo(), FakeDiffContext(), _make_config())
            assert isinstance(result, SummaryResult)
            assert result.summary == data["summary"]

    def test_passes_messages_to_llm(self):
        import json
        resp = _make_response(json.dumps(_sample_summary_json()))
        with patch("src.summary_analyzer.chat_completion", return_value=resp) as mock_cc:
            generate_pr_summary(FakePRInfo(), FakeDiffContext(), _make_config())
            messages = mock_cc.call_args[0][0]
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    def test_passes_config_to_llm(self):
        import json
        resp = _make_response(json.dumps(_sample_summary_json()))
        cfg = _make_config()
        with patch("src.summary_analyzer.chat_completion", return_value=resp) as mock_cc:
            generate_pr_summary(FakePRInfo(), FakeDiffContext(), cfg)
            assert mock_cc.call_args[0][1] == cfg
