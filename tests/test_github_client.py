"""Tests for GitHub PR info client."""

from unittest.mock import MagicMock, patch

import pytest

from src.github_client import (
    GitHubClientError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubUnauthorizedError,
    PRInfo,
    fetch_pr_info,
)


def _mock_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or {}
    resp.headers = headers or {}
    return resp


def _sample_api_response(**overrides):
    data = {
        "title": "Add login validation",
        "user": {"login": "dev123"},
        "state": "closed",
        "merged": True,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "closed_at": "2026-01-02T00:00:00Z",
        "merged_at": "2026-01-02T00:00:00Z",
        "body": "This PR adds input validation to the login form.",
        "changed_files": 3,
        "additions": 42,
        "deletions": 10,
        "commits": 2,
        "html_url": "https://github.com/owner/repo/pull/123",
    }
    data.update(overrides)
    return data


class TestFetchPRInfoSuccess:
    def test_returns_prinfo(self):
        resp = _mock_response(200, _sample_api_response())
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_info("owner", "repo", 123)
            assert isinstance(result, PRInfo)

    def test_fields_mapped_correctly(self):
        resp = _mock_response(200, _sample_api_response())
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            result = fetch_pr_info("owner", "repo", 123)
            assert result.owner == "owner"
            assert result.repo == "repo"
            assert result.pull_number == 123
            assert result.title == "Add login validation"
            assert result.author == "dev123"
            assert result.state == "closed"
            assert result.merged is True
            assert result.created_at == "2026-01-01T00:00:00Z"
            assert result.closed_at == "2026-01-02T00:00:00Z"
            assert result.merged_at == "2026-01-02T00:00:00Z"
            assert result.body == "This PR adds input validation to the login form."
            assert result.changed_files == 3
            assert result.additions == 42
            assert result.deletions == 10
            assert result.commits == 2
            assert result.html_url == "https://github.com/owner/repo/pull/123"

    def test_body_none_converted_to_empty_string(self):
        resp = _mock_response(200, _sample_api_response(body=None))
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_info("o", "r", 1)
            assert result.body == ""

    def test_accept_header_set(self):
        resp = _mock_response(200, _sample_api_response())
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_info("o", "r", 1)
            headers = mock_get.call_args[1]["headers"]
            assert "Accept" in headers
            assert "User-Agent" in headers
            assert headers["Accept"] == "application/vnd.github+json"
            assert headers["User-Agent"] == "PRLens"

    def test_no_auth_without_token(self):
        resp = _mock_response(200, _sample_api_response())
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_info("o", "r", 1)
            headers = mock_get.call_args[1]["headers"]
            assert "Authorization" not in headers

    def test_auth_header_with_token(self):
        resp = _mock_response(200, _sample_api_response())
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_info("o", "r", 1, token="ghp_test123")
            headers = mock_get.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer ghp_test123"

    def test_optional_fields_none(self):
        resp = _mock_response(200, _sample_api_response(closed_at=None, merged_at=None))
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_info("o", "r", 1)
            assert result.closed_at is None
            assert result.merged_at is None

    def test_unmerged_pr(self):
        resp = _mock_response(200, _sample_api_response(merged=False, merged_at=None))
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_info("o", "r", 1)
            assert result.merged is False
            assert result.merged_at is None


class TestFetchPRInfoErrors:
    def test_401_raises_unauthorized(self):
        resp = _mock_response(401, {"message": "Bad credentials"})
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubUnauthorizedError):
                fetch_pr_info("o", "r", 1)

    def test_403_rate_limit_raises_rate_limit_error(self):
        resp = _mock_response(403, {}, headers={"X-RateLimit-Remaining": "0"})
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubRateLimitError):
                fetch_pr_info("o", "r", 1)

    def test_404_raises_not_found(self):
        resp = _mock_response(404)
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubNotFoundError):
                fetch_pr_info("o", "r", 1)

    def test_500_raises_client_error(self):
        resp = _mock_response(500)
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubClientError):
                fetch_pr_info("o", "r", 1)

    def test_network_error_raises_client_error(self):
        import requests as rq
        with patch("src.github_client.requests.get",
                   side_effect=rq.ConnectionError("Connection refused")):
            with pytest.raises(GitHubClientError):
                fetch_pr_info("o", "r", 1)

    def test_json_parse_failure_raises_client_error(self):
        resp = _mock_response(200, None)
        resp.json.side_effect = ValueError("Invalid JSON")
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubClientError):
                fetch_pr_info("o", "r", 1)
