"""LLM client for OpenAI-compatible Chat Completions API."""

import os
from dataclasses import dataclass
from typing import Any, Optional

import requests


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMConfig:
    api_key: str
    model: str
    base_url: str
    timeout: int = 60
    temperature: float = 0.2
    max_tokens: int = 1200


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, Any]
    raw_response: dict[str, Any]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMClientError(RuntimeError):
    pass


class LLMConfigError(LLMClientError):
    pass


class LLMUnauthorizedError(LLMClientError):
    pass


class LLMRateLimitError(LLMClientError):
    pass


class LLMResponseError(LLMClientError):
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_llm_config_from_env() -> LLMConfig:
    """Load LLM configuration from environment variables.

    Required: LLM_API_KEY, LLM_MODEL, LLM_BASE_URL.
    Optional: LLM_TIMEOUT (default 60), LLM_TEMPERATURE (default 0.2),
              LLM_MAX_TOKENS (default 1200).

    Raises:
        LLMConfigError: If a required variable is missing or numeric parsing fails.
    """
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        raise LLMConfigError("LLM_API_KEY is required but not set.")

    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise LLMConfigError("LLM_MODEL is required but not set.")

    base_url = os.getenv("LLM_BASE_URL", "").strip()
    if not base_url:
        raise LLMConfigError("LLM_BASE_URL is required but not set.")

    timeout = _parse_int_env("LLM_TIMEOUT", 60)
    temperature = _parse_float_env("LLM_TEMPERATURE", 0.2)
    max_tokens = _parse_int_env("LLM_MAX_TOKENS", 1200)

    return LLMConfig(
        api_key=api_key,
        model=model,
        base_url=base_url,
        timeout=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise LLMConfigError(f"{name} must be an integer, got: {raw}")


def _parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        raise LLMConfigError(f"{name} must be a number, got: {raw}")


# ---------------------------------------------------------------------------
# Chat Completions
# ---------------------------------------------------------------------------


def chat_completion(
    messages: list[dict[str, str]],
    config: LLMConfig,
) -> LLMResponse:
    """Send a chat completion request and return the parsed response.

    Args:
        messages: List of message dicts with "role" and "content" keys.
        config: LLM configuration.

    Returns:
        LLMResponse with content, model, usage, and raw response data.

    Raises:
        ValueError: If messages is empty.
        LLMConfigError: If config is missing required fields.
        LLMUnauthorizedError: On 401 or 403 responses.
        LLMRateLimitError: On 429 responses.
        LLMClientError: On 400, 5xx, or network failures.
        LLMResponseError: On JSON parse failures or unexpected response structure.
    """
    if not messages:
        raise ValueError("messages must not be empty")

    if not config.api_key:
        raise LLMConfigError("api_key is required")
    if not config.model:
        raise LLMConfigError("model is required")
    if not config.base_url:
        raise LLMConfigError("base_url is required")

    url = config.base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=config.timeout)
    except requests.RequestException as e:
        raise LLMClientError(f"Network error calling LLM API: {e}") from e

    if resp.status_code == 401 or resp.status_code == 403:
        raise LLMUnauthorizedError(
            f"LLM authentication failed ({resp.status_code}). Check your API key."
        )
    if resp.status_code == 429:
        raise LLMRateLimitError("LLM rate limit exceeded. Wait and retry.")
    if resp.status_code == 400:
        raise LLMClientError(f"LLM bad request (400): {resp.text[:200]}")
    if resp.status_code >= 500:
        raise LLMClientError(f"LLM server error ({resp.status_code}): {resp.text[:200]}")

    if not resp.ok:
        raise LLMClientError(f"LLM HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise LLMResponseError(f"Failed to parse LLM JSON response: {e}") from e

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMResponseError(
            f"Unexpected LLM response structure: missing choices/message/content. "
            f"Keys received: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        ) from e

    return LLMResponse(
        content=content,
        model=data.get("model", config.model),
        usage=data.get("usage", {}),
        raw_response=data,
    )
