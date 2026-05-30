"""Tests for GitHub PR info client."""

from unittest.mock import MagicMock, patch

import pytest

from src.github_client import (
    ChangedFile,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubUnauthorizedError,
    PRInfo,
    fetch_pr_files,
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


# ---------------------------------------------------------------------------
# fetch_pr_files helpers
# ---------------------------------------------------------------------------


def _sample_file(**overrides):
    data = {
        "filename": "src/login.py",
        "status": "modified",
        "additions": 10,
        "deletions": 3,
        "changes": 13,
        "patch": "@@ -1,3 +1,10 @@\n+def validate(): pass",
        "sha": "abc123",
        "blob_url": "https://api.github.com/repos/owner/repo/git/blobs/abc123",
        "raw_url": "https://api.github.com/repos/owner/repo/raw/src/login.py",
        "contents_url": "https://api.github.com/repos/owner/repo/contents/src/login.py",
    }
    data.update(overrides)
    return data


def _mock_file_response(status_code=200, json_data=None, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data or []
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# fetch_pr_files success tests
# ---------------------------------------------------------------------------


class TestFetchPRFilesSuccess:
    def test_returns_list_of_changedfile(self):
        resp = _mock_file_response(200, [_sample_file()])
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_files("o", "r", 1)
            assert len(result) == 1
            assert isinstance(result[0], ChangedFile)

    def test_fields_mapped_correctly(self):
        resp = _mock_file_response(200, [_sample_file()])
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_files("o", "r", 1)
            f = result[0]
            assert f.filename == "src/login.py"
            assert f.status == "modified"
            assert f.additions == 10
            assert f.deletions == 3
            assert f.changes == 13
            assert "validate" in f.patch
            assert f.sha == "abc123"
            assert "blobs" in f.blob_url

    def test_patch_none_converted_to_empty_string(self):
        resp = _mock_file_response(200, [_sample_file(patch=None)])
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_files("o", "r", 1)
            assert result[0].patch == ""

    def test_missing_numeric_defaults_to_zero(self):
        resp = _mock_file_response(200, [_sample_file(additions=None, deletions=None, changes=None)])
        with patch("src.github_client.requests.get", return_value=resp):
            result = fetch_pr_files("o", "r", 1)
            assert result[0].additions == 0
            assert result[0].deletions == 0
            assert result[0].changes == 0

    def test_accept_and_user_agent_headers(self):
        resp = _mock_file_response(200, [_sample_file()])
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_files("o", "r", 1)
            headers = mock_get.call_args[1]["headers"]
            assert headers["Accept"] == "application/vnd.github+json"
            assert headers["User-Agent"] == "PRLens"

    def test_auth_header_with_token(self):
        resp = _mock_file_response(200, [_sample_file()])
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_files("o", "r", 1, token="ghp_test")
            headers = mock_get.call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer ghp_test"

    def test_no_auth_without_token(self):
        resp = _mock_file_response(200, [_sample_file()])
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            fetch_pr_files("o", "r", 1)
            assert "Authorization" not in mock_get.call_args[1]["headers"]


# ---------------------------------------------------------------------------
# fetch_pr_files pagination tests
# ---------------------------------------------------------------------------


class TestFetchPRFilesPagination:
    def test_multi_page_merges_results(self):
        page1 = [_sample_file(filename="a.py")]
        page2 = [_sample_file(filename="b.py")]
        page3 = []
        resp1 = _mock_file_response(200, page1)
        resp2 = _mock_file_response(200, page2)
        resp3 = _mock_file_response(200, page3)
        with patch("src.github_client.requests.get",
                   side_effect=[resp1, resp2, resp3]) as mock_get:
            result = fetch_pr_files("o", "r", 1, per_page=1)
            assert len(result) == 2
            assert result[0].filename == "a.py"
            assert result[1].filename == "b.py"
            assert mock_get.call_count == 3

    def test_empty_page_stops_pagination(self):
        resp1 = _mock_file_response(200, [_sample_file()])
        resp2 = _mock_file_response(200, [])
        with patch("src.github_client.requests.get", side_effect=[resp1, resp2]) as mock_get:
            result = fetch_pr_files("o", "r", 1, per_page=1)
            assert len(result) == 1
            assert mock_get.call_count == 2

    def test_max_files_stops_collection(self):
        resp = _mock_file_response(200, [_sample_file(), _sample_file(), _sample_file()])
        with patch("src.github_client.requests.get", return_value=resp) as mock_get:
            result = fetch_pr_files("o", "r", 1, max_files=2)
            assert len(result) == 2
            assert mock_get.call_count == 1


# ---------------------------------------------------------------------------
# fetch_pr_files validation tests
# ---------------------------------------------------------------------------


class TestFetchPRFilesValidation:
    def test_per_page_below_1_raises_value_error(self):
        with pytest.raises(ValueError, match="per_page"):
            fetch_pr_files("o", "r", 1, per_page=0)

    def test_per_page_above_100_raises_value_error(self):
        with pytest.raises(ValueError, match="per_page"):
            fetch_pr_files("o", "r", 1, per_page=101)

    def test_max_files_below_1_raises_value_error(self):
        with pytest.raises(ValueError, match="max_files"):
            fetch_pr_files("o", "r", 1, max_files=0)


# ---------------------------------------------------------------------------
# fetch_pr_files error tests
# ---------------------------------------------------------------------------


class TestFetchPRFilesErrors:
    def test_401_raises_unauthorized(self):
        resp = _mock_file_response(401, {"message": "Bad credentials"})
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubUnauthorizedError):
                fetch_pr_files("o", "r", 1)

    def test_403_rate_limit(self):
        resp = _mock_file_response(403, {}, headers={"X-RateLimit-Remaining": "0"})
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubRateLimitError):
                fetch_pr_files("o", "r", 1)

    def test_404_raises_not_found(self):
        resp = _mock_file_response(404)
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubNotFoundError):
                fetch_pr_files("o", "r", 1)

    def test_422_raises_client_error(self):
        resp = _mock_file_response(422)
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubClientError):
                fetch_pr_files("o", "r", 1)

    def test_500_raises_client_error(self):
        resp = _mock_file_response(500)
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubClientError):
                fetch_pr_files("o", "r", 1)

    def test_network_error_raises_client_error(self):
        import requests as rq
        with patch("src.github_client.requests.get",
                   side_effect=rq.ConnectionError("Connection refused")):
            with pytest.raises(GitHubClientError):
                fetch_pr_files("o", "r", 1)

    def test_non_list_response_raises_client_error(self):
        resp = _mock_file_response(200, {"message": "not an array"})
        resp.json.return_value = {"message": "not an array"}
        with patch("src.github_client.requests.get", return_value=resp):
            with pytest.raises(GitHubClientError):
                fetch_pr_files("o", "r", 1)
