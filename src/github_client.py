"""GitHub REST API client for fetching PR basic information."""

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class PRInfo:
    owner: str
    repo: str
    pull_number: int
    title: str
    author: str
    state: str
    merged: bool
    created_at: str
    updated_at: str
    closed_at: Optional[str]
    merged_at: Optional[str]
    body: str
    changed_files: int
    additions: int
    deletions: int
    commits: int
    html_url: str


class GitHubClientError(RuntimeError):
    pass


class GitHubNotFoundError(GitHubClientError):
    pass


class GitHubRateLimitError(GitHubClientError):
    pass


class GitHubUnauthorizedError(GitHubClientError):
    pass


def fetch_pr_info(owner: str, repo: str, pull_number: int, token: Optional[str] = None) -> PRInfo:
    """Fetch PR basic information from GitHub REST API.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: PR number.
        token: Optional GitHub personal access token.

    Returns:
        PRInfo with structured PR data.

    Raises:
        GitHubUnauthorizedError: 401 response.
        GitHubRateLimitError: 403 with rate limit exhausted.
        GitHubNotFoundError: 404 response.
        GitHubClientError: Other HTTP errors, network failures, or parse errors.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PRLens",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        raise GitHubClientError(f"Network error: {e}") from e

    if resp.status_code == 401:
        raise GitHubUnauthorizedError("Invalid or missing GitHub token (401 Unauthorized).")
    if resp.status_code == 403:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            raise GitHubRateLimitError("GitHub API rate limit exceeded. Consider adding a token or waiting before retrying.")
        raise GitHubClientError(f"Access forbidden (403): {resp.text[:200]}")
    if resp.status_code == 404:
        raise GitHubNotFoundError(f"PR not found: {owner}/{repo}/pull/{pull_number}")
    if not resp.ok:
        raise GitHubClientError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise GitHubClientError(f"Failed to parse JSON response: {e}") from e

    try:
        return _map_response_to_prinfo(data, owner, repo, pull_number)
    except (KeyError, TypeError) as e:
        raise GitHubClientError(f"Missing or invalid field in API response: {e}") from e


def _map_response_to_prinfo(data: dict, owner: str, repo: str, pull_number: int) -> PRInfo:
    """Map GitHub API response dict to PRInfo dataclass."""
    return PRInfo(
        owner=owner,
        repo=repo,
        pull_number=pull_number,
        title=data["title"],
        author=data["user"]["login"],
        state=data["state"],
        merged=bool(data.get("merged", False)),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        closed_at=data.get("closed_at"),
        merged_at=data.get("merged_at"),
        body=data.get("body") or "",
        changed_files=int(data.get("changed_files", 0)),
        additions=int(data.get("additions", 0)),
        deletions=int(data.get("deletions", 0)),
        commits=int(data.get("commits", 0)),
        html_url=data["html_url"],
    )
