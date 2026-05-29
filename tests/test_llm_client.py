"""Tests for LLM client (all mocked, zero real API calls)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.llm_client import (
    LLMClientError,
    LLMConfig,
    LLMConfigError,
    LLMRateLimitError,
    LLMResponse,
    LLMResponseError,
    LLMUnauthorizedError,
    chat_completion,
    load_llm_config_from_env,
)


def _mock_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    return resp


def _sample_llm_json(content="Hello"):
    return {
        "choices": [{"message": {"content": content}}],
        "model": "test-model",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _make_config(**kw):
    return LLMConfig(
        api_key=kw.get("api_key", "sk-test"),
        model=kw.get("model", "test-model"),
        base_url=kw.get("base_url", "https://api.example.com/v1"),
        timeout=kw.get("timeout", 60),
        temperature=kw.get("temperature", 0.2),
        max_tokens=kw.get("max_tokens", 1200),
    )


# ---------------------------------------------------------------------------
# load_llm_config_from_env
# ---------------------------------------------------------------------------


class TestLoadConfigSuccess:
    def test_reads_required_vars(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
        cfg = load_llm_config_from_env()
        assert cfg.api_key == "sk-abc"
        assert cfg.model == "gpt-4"
        assert cfg.base_url == "https://api.openai.com/v1"

    def test_default_values(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
        cfg = load_llm_config_from_env()
        assert cfg.timeout == 60
        assert cfg.temperature == 0.2
        assert cfg.max_tokens == 1200

    def test_custom_optional_values(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("LLM_TIMEOUT", "30")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.5")
        monkeypatch.setenv("LLM_MAX_TOKENS", "2000")
        cfg = load_llm_config_from_env()
        assert cfg.timeout == 30
        assert cfg.temperature == 0.5
        assert cfg.max_tokens == 2000

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "  sk-abc  ")
        monkeypatch.setenv("LLM_MODEL", "  gpt-4  ")
        monkeypatch.setenv("LLM_BASE_URL", "  https://api.openai.com/v1  ")
        cfg = load_llm_config_from_env()
        assert cfg.api_key == "sk-abc"
        assert cfg.model == "gpt-4"
        assert cfg.base_url == "https://api.openai.com/v1"


class TestLoadConfigErrors:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://x.com/v1")
        with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
            load_llm_config_from_env()

    def test_missing_model(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        monkeypatch.setenv("LLM_BASE_URL", "https://x.com/v1")
        with pytest.raises(LLMConfigError, match="LLM_MODEL"):
            load_llm_config_from_env()

    def test_missing_base_url(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        with pytest.raises(LLMConfigError, match="LLM_BASE_URL"):
            load_llm_config_from_env()

    def test_invalid_timeout(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://x.com/v1")
        monkeypatch.setenv("LLM_TIMEOUT", "not-a-number")
        with pytest.raises(LLMConfigError, match="LLM_TIMEOUT"):
            load_llm_config_from_env()

    def test_invalid_temperature(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://x.com/v1")
        monkeypatch.setenv("LLM_TEMPERATURE", "abc")
        with pytest.raises(LLMConfigError, match="LLM_TEMPERATURE"):
            load_llm_config_from_env()

    def test_invalid_max_tokens(self, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "sk-abc")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")
        monkeypatch.setenv("LLM_BASE_URL", "https://x.com/v1")
        monkeypatch.setenv("LLM_MAX_TOKENS", "abc")
        with pytest.raises(LLMConfigError, match="LLM_MAX_TOKENS"):
            load_llm_config_from_env()


# ---------------------------------------------------------------------------
# chat_completion success
# ---------------------------------------------------------------------------


class TestChatCompletionSuccess:
    def test_returns_llm_response(self):
        resp = _mock_resp(200, _sample_llm_json("Hello, world"))
        with patch("src.llm_client.requests.post", return_value=resp):
            result = chat_completion(
                [{"role": "user", "content": "Hi"}], _make_config()
            )
            assert isinstance(result, LLMResponse)
            assert result.content == "Hello, world"
            assert result.model == "test-model"
            assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5}

    def test_url_constructed_correctly(self):
        resp = _mock_resp(200, _sample_llm_json())
        with patch("src.llm_client.requests.post", return_value=resp) as mock_post:
            cfg = _make_config(base_url="https://api.example.com/v1/")
            chat_completion([{"role": "user", "content": "X"}], cfg)
            url = mock_post.call_args[0][0]
            assert url == "https://api.example.com/v1/chat/completions"

    def test_request_headers(self):
        resp = _mock_resp(200, _sample_llm_json())
        with patch("src.llm_client.requests.post", return_value=resp) as mock_post:
            chat_completion([{"role": "user", "content": "X"}], _make_config())
            headers = mock_post.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer sk-test"
            assert headers["Content-Type"] == "application/json"

    def test_request_body(self):
        resp = _mock_resp(200, _sample_llm_json())
        with patch("src.llm_client.requests.post", return_value=resp) as mock_post:
            cfg = _make_config(temperature=0.3, max_tokens=500)
            chat_completion([{"role": "system", "content": "Be helpful"}], cfg)
            body = mock_post.call_args[1]["json"]
            assert body["model"] == "test-model"
            assert body["temperature"] == 0.3
            assert body["max_tokens"] == 500
            assert body["messages"] == [{"role": "system", "content": "Be helpful"}]

    def test_timeout_applied(self):
        resp = _mock_resp(200, _sample_llm_json())
        with patch("src.llm_client.requests.post", return_value=resp) as mock_post:
            cfg = _make_config(timeout=30)
            chat_completion([{"role": "user", "content": "X"}], cfg)
            assert mock_post.call_args[1]["timeout"] == 30

    def test_model_falls_back_to_config(self):
        data = _sample_llm_json()
        del data["model"]
        resp = _mock_resp(200, data)
        with patch("src.llm_client.requests.post", return_value=resp):
            result = chat_completion(
                [{"role": "user", "content": "X"}], _make_config()
            )
            assert result.model == "test-model"


# ---------------------------------------------------------------------------
# chat_completion validation
# ---------------------------------------------------------------------------


class TestChatCompletionValidation:
    def test_empty_messages_raises_value_error(self):
        with pytest.raises(ValueError, match="messages"):
            chat_completion([], _make_config())

    def test_empty_api_key_raises_config_error(self):
        with pytest.raises(LLMConfigError, match="api_key"):
            chat_completion(
                [{"role": "user", "content": "X"}], _make_config(api_key="")
            )

    def test_empty_model_raises_config_error(self):
        with pytest.raises(LLMConfigError, match="model"):
            chat_completion(
                [{"role": "user", "content": "X"}], _make_config(model="")
            )

    def test_empty_base_url_raises_config_error(self):
        with pytest.raises(LLMConfigError, match="base_url"):
            chat_completion(
                [{"role": "user", "content": "X"}], _make_config(base_url="")
            )


# ---------------------------------------------------------------------------
# chat_completion HTTP errors
# ---------------------------------------------------------------------------


class TestChatCompletionHTTPErrors:
    def test_401_raises_unauthorized(self):
        resp = _mock_resp(401)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMUnauthorizedError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_403_raises_unauthorized(self):
        resp = _mock_resp(403)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMUnauthorizedError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_429_raises_rate_limit(self):
        resp = _mock_resp(429)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMRateLimitError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_400_raises_client_error(self):
        resp = _mock_resp(400)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMClientError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_500_raises_client_error(self):
        resp = _mock_resp(500)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMClientError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_network_error_raises_client_error(self):
        import requests as rq
        with patch("src.llm_client.requests.post",
                   side_effect=rq.ConnectionError("refused")):
            with pytest.raises(LLMClientError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())


# ---------------------------------------------------------------------------
# chat_completion response errors
# ---------------------------------------------------------------------------


class TestChatCompletionResponseErrors:
    def test_json_parse_failure(self):
        resp = _mock_resp(200)
        resp.json.side_effect = ValueError("bad json")
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMResponseError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_missing_choices(self):
        resp = _mock_resp(200, {"no_choices": True})
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMResponseError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_missing_message(self):
        resp = _mock_resp(200, {"choices": [{}]})
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMResponseError):
                chat_completion([{"role": "user", "content": "X"}], _make_config())

    def test_error_message_does_not_leak_api_key(self):
        resp = _mock_resp(401)
        with patch("src.llm_client.requests.post", return_value=resp):
            with pytest.raises(LLMUnauthorizedError) as exc:
                chat_completion(
                    [{"role": "user", "content": "X"}],
                    _make_config(api_key="sk-secret123"),
                )
            assert "sk-secret123" not in str(exc.value)
