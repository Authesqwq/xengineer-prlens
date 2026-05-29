"""GitHub Pull Request URL parser."""

import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class ParsedPR:
    owner: str
    repo: str
    pull_number: int
    url: str


class PRUrlParseError(ValueError):
    pass


# Matches: github.com or www.github.com, path: /owner/repo/pull/number
_PR_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com"
    r"/([^/]+)/([^/]+)/pull/(\d+)"
    r"(?:/.*)?(?:\?.*)?(?:#.*)?$",
    re.IGNORECASE,
)


def parse_github_pr_url(url: str) -> ParsedPR:
    """Parse a GitHub PR URL and return ParsedPR.

    Args:
        url: Raw GitHub PR URL string.

    Returns:
        ParsedPR with owner, repo, pull_number, and normalized url.

    Raises:
        PRUrlParseError: If the URL does not match a GitHub PR pattern.
    """
    if not url or not url.strip():
        raise PRUrlParseError(
            "请输入正确的 GitHub PR 链接，例如：https://github.com/owner/repo/pull/123"
        )

    url = url.strip()

    match = _PR_PATTERN.match(url)
    if not match:
        raise PRUrlParseError(
            "请输入正确的 GitHub PR 链接，例如：https://github.com/owner/repo/pull/123"
        )

    owner = match.group(1)
    repo = match.group(2)
    pull_number = int(match.group(3))

    if not owner or not repo:
        raise PRUrlParseError(
            "请输入正确的 GitHub PR 链接，例如：https://github.com/owner/repo/pull/123"
        )

    return ParsedPR(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        url=url,
    )
