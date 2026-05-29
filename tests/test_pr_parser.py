"""Tests for GitHub PR URL parser."""

import pytest

from src.pr_parser import ParsedPR, PRUrlParseError, parse_github_pr_url


class TestValidUrls:
    def test_https_standard(self):
        result = parse_github_pr_url("https://github.com/owner/repo/pull/123")
        assert result == ParsedPR("owner", "repo", 123, "https://github.com/owner/repo/pull/123")

    def test_http(self):
        result = parse_github_pr_url("http://github.com/owner/repo/pull/123")
        assert result.owner == "owner"
        assert result.repo == "repo"
        assert result.pull_number == 123

    def test_no_protocol(self):
        result = parse_github_pr_url("github.com/owner/repo/pull/123")
        assert result.pull_number == 123

    def test_www_prefix(self):
        result = parse_github_pr_url("https://www.github.com/owner/repo/pull/123")
        assert result.owner == "owner"
        assert result.repo == "repo"
        assert result.pull_number == 123

    def test_trailing_files(self):
        result = parse_github_pr_url("https://github.com/owner/repo/pull/123/files")
        assert result.pull_number == 123

    def test_query_params(self):
        result = parse_github_pr_url("https://github.com/owner/repo/pull/123?tab=conversation")
        assert result.pull_number == 123

    def test_fragment(self):
        result = parse_github_pr_url(
            "https://github.com/owner/repo/pull/123#discussion_r123456"
        )
        assert result.pull_number == 123

    def test_whitespace_stripped(self):
        result = parse_github_pr_url("  https://github.com/owner/repo/pull/123  ")
        assert result.url == "https://github.com/owner/repo/pull/123"
        assert result.pull_number == 123

    def test_pull_number_is_int(self):
        result = parse_github_pr_url("https://github.com/owner/repo/pull/1")
        assert result.pull_number == 1
        assert isinstance(result.pull_number, int)

    def test_large_pr_number(self):
        result = parse_github_pr_url("https://github.com/owner/repo/pull/99999")
        assert result.pull_number == 99999


class TestInvalidUrls:
    def test_empty_string(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("")

    def test_whitespace_only(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("   ")

    def test_random_text(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("hello")

    def test_gitlab_url(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("https://gitlab.com/owner/repo/pull/123")

    def test_issues_not_pull(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("https://github.com/owner/repo/issues/123")

    def test_no_pull_path(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("https://github.com/owner/repo")

    def test_non_numeric_pr(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("https://github.com/owner/repo/pull/abc")

    def test_empty_pr_number(self):
        with pytest.raises(PRUrlParseError):
            parse_github_pr_url("https://github.com/owner/repo/pull/")
