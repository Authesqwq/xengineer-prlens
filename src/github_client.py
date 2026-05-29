"""GitHub REST API client for fetching PR information and changed files."""

from dataclasses import dataclass
from typing import Optional

import requests


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


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


@dataclass
class ChangedFile:
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str
    sha: Optional[str] = None
    blob_url: Optional[str] = None
    raw_url: Optional[str] = None
    contents_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubClientError(RuntimeError):
    pass


class GitHubNotFoundError(GitHubClientError):
    pass


class GitHubRateLimitError(GitHubClientError):
    pass


class GitHubUnauthorizedError(GitHubClientError):
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_headers(token: Optional[str] = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PRLens",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _do_request(url: str, headers: dict, params: Optional[dict] = None) -> requests.Response:
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.RequestException as e:
        raise GitHubClientError(f"Network error: {e}") from e

    if resp.status_code == 401:
        raise GitHubUnauthorizedError("Invalid or missing GitHub token (401 Unauthorized).")
    if resp.status_code == 403:
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) == 0:
            raise GitHubRateLimitError(
                "GitHub API rate limit exceeded. Consider adding a token or waiting before retrying."
            )
        raise GitHubClientError(f"Access forbidden (403): {resp.text[:200]}")
    if resp.status_code == 404:
        raise GitHubNotFoundError(f"Resource not found: {url}")
    if not resp.ok:
        raise GitHubClientError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    return resp


def _parse_json(resp: requests.Response) -> object:
    try:
        return resp.json()
    except ValueError as e:
        raise GitHubClientError(f"Failed to parse JSON response: {e}") from e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_pr_info(owner: str, repo: str, pull_number: int, token: Optional[str] = None) -> PRInfo:
    """Fetch PR basic information from GitHub REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    headers = _build_headers(token)
    resp = _do_request(url, headers)
    data = _parse_json(resp)

    try:
        return _map_response_to_prinfo(data, owner, repo, pull_number)
    except (KeyError, TypeError) as e:
        raise GitHubClientError(f"Missing or invalid field in API response: {e}") from e


def fetch_pr_files(
    owner: str,
    repo: str,
    pull_number: int,
    token: Optional[str] = None,
    per_page: int = 100,
    max_files: int = 3000,
) -> list[ChangedFile]:
    """Fetch changed files and patches for a PR.

    Args:
        owner: Repository owner.
        repo: Repository name.
        pull_number: PR number.
        token: Optional GitHub personal access token.
        per_page: Files per page (1-100).
        max_files: Maximum total files to return.

    Returns:
        List of ChangedFile objects.

    Raises:
        ValueError: If per_page or max_files are out of range.
        GitHubUnauthorizedError: 401 response.
        GitHubRateLimitError: 403 with rate limit exhausted.
        GitHubNotFoundError: 404 response.
        GitHubClientError: Other HTTP errors, network failures, or parse errors.
    """
    if per_page < 1 or per_page > 100:
        raise ValueError("per_page must be between 1 and 100")
    if max_files < 1:
        raise ValueError("max_files must be at least 1")

    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}/files"
    headers = _build_headers(token)

    all_files = []
    page = 1

    while len(all_files) < max_files:
        params = {"per_page": per_page, "page": page}
        resp = _do_request(url, headers, params)
        data = _parse_json(resp)

        if not isinstance(data, list):
            raise GitHubClientError(f"Expected JSON array, got {type(data).__name__}")

        if not data:
            break

        remaining = max_files - len(all_files)
        batch = data[:remaining]
        all_files.extend(_map_response_to_changedfile(f) for f in batch)

        if len(data) < per_page:
            break
        page += 1

    return all_files


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _map_response_to_prinfo(data: dict, owner: str, repo: str, pull_number: int) -> PRInfo:
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


def _map_response_to_changedfile(data: dict) -> ChangedFile:
    return ChangedFile(
        filename=data["filename"],
        status=data.get("status", ""),
        additions=int(data.get("additions") or 0),
        deletions=int(data.get("deletions") or 0),
        changes=int(data.get("changes") or 0),
        patch=data.get("patch") or "",
        sha=data.get("sha"),
        blob_url=data.get("blob_url"),
        raw_url=data.get("raw_url"),
        contents_url=data.get("contents_url"),
    )
