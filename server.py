"""
GitHub MCP Server
-----------------
An MCP server that exposes GitHub API functionality as tools,
allowing any MCP-compatible AI client (e.g. Claude Desktop) to
interact with GitHub repos, issues, and pull requests.
"""

import os
import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Initialise the server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="github-mcp-server",
    instructions=(
        "You have access to GitHub tools. Use them to search repos, manage "
        "issues, inspect pull requests, and retrieve file contents. Always "
        "confirm destructive actions (creating / closing issues, etc.) before "
        "proceeding."
    ),
)

GITHUB_API = "https://api.github.com"


# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------

def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError(
            "GITHUB_TOKEN environment variable is not set. "
            "Create a Personal Access Token at https://github.com/settings/tokens "
            "and export it before starting the server."
        )
    return token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(path: str, params: dict | None = None) -> dict | list:
    """Synchronous GET against the GitHub REST API."""
    with httpx.Client(timeout=15) as client:
        response = client.get(f"{GITHUB_API}{path}", headers=_headers(), params=params)
        response.raise_for_status()
        return response.json()


def _post(path: str, body: dict) -> dict:
    """Synchronous POST against the GitHub REST API."""
    with httpx.Client(timeout=15) as client:
        response = client.post(f"{GITHUB_API}{path}", headers=_headers(), json=body)
        response.raise_for_status()
        return response.json()


def _patch(path: str, body: dict) -> dict:
    """Synchronous PATCH against the GitHub REST API."""
    with httpx.Client(timeout=15) as client:
        response = client.patch(f"{GITHUB_API}{path}", headers=_headers(), json=body)
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Tool: get_authenticated_user
# ---------------------------------------------------------------------------

@mcp.tool()
def get_authenticated_user() -> dict:
    """
    Return the profile of the currently authenticated GitHub user.

    Returns a dict with fields: login, name, email, bio, public_repos,
    followers, following, html_url, created_at.
    """
    raw = _get("/user")
    return {
        "login": raw.get("login"),
        "name": raw.get("name"),
        "email": raw.get("email"),
        "bio": raw.get("bio"),
        "public_repos": raw.get("public_repos"),
        "followers": raw.get("followers"),
        "following": raw.get("following"),
        "html_url": raw.get("html_url"),
        "created_at": raw.get("created_at"),
    }


# ---------------------------------------------------------------------------
# Tool: search_repositories
# ---------------------------------------------------------------------------

@mcp.tool()
def search_repositories(query: str, sort: str = "stars", per_page: int = 10) -> list[dict]:
    """
    Search GitHub repositories by keyword.

    Args:
        query:    GitHub search query string, e.g. "mcp server language:python".
        sort:     Sort field — one of "stars", "forks", "updated". Default "stars".
        per_page: Number of results to return (1–30). Default 10.

    Returns a list of dicts, each with: full_name, description, stars,
    forks, language, html_url, updated_at.
    """
    per_page = max(1, min(per_page, 30))
    data = _get("/search/repositories", params={"q": query, "sort": sort, "per_page": per_page})
    results = []
    for item in data.get("items", []):
        results.append({
            "full_name": item["full_name"],
            "description": item.get("description"),
            "stars": item["stargazers_count"],
            "forks": item["forks_count"],
            "language": item.get("language"),
            "html_url": item["html_url"],
            "updated_at": item["updated_at"],
        })
    return results


# ---------------------------------------------------------------------------
# Tool: get_repository
# ---------------------------------------------------------------------------

@mcp.tool()
def get_repository(owner: str, repo: str) -> dict:
    """
    Fetch metadata for a specific GitHub repository.

    Args:
        owner: GitHub username or organisation, e.g. "octocat".
        repo:  Repository name, e.g. "hello-world".

    Returns a dict with: full_name, description, stars, forks, open_issues,
    language, default_branch, license, topics, html_url, created_at, updated_at.
    """
    raw = _get(f"/repos/{owner}/{repo}")
    return {
        "full_name": raw["full_name"],
        "description": raw.get("description"),
        "stars": raw["stargazers_count"],
        "forks": raw["forks_count"],
        "open_issues": raw["open_issues_count"],
        "language": raw.get("language"),
        "default_branch": raw["default_branch"],
        "license": raw.get("license", {}).get("name") if raw.get("license") else None,
        "topics": raw.get("topics", []),
        "html_url": raw["html_url"],
        "created_at": raw["created_at"],
        "updated_at": raw["updated_at"],
    }


# ---------------------------------------------------------------------------
# Tool: list_issues
# ---------------------------------------------------------------------------

@mcp.tool()
def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    labels: str = "",
    per_page: int = 20,
) -> list[dict]:
    """
    List issues for a repository (excludes pull requests).

    Args:
        owner:    Repository owner.
        repo:     Repository name.
        state:    "open", "closed", or "all". Default "open".
        labels:   Comma-separated label names to filter by, e.g. "bug,help wanted".
        per_page: Number of issues to return (1–50). Default 20.

    Returns a list of dicts with: number, title, state, labels, author,
    created_at, updated_at, html_url, body_preview.
    """
    per_page = max(1, min(per_page, 50))
    params: dict = {"state": state, "per_page": per_page}
    if labels:
        params["labels"] = labels

    raw_list = _get(f"/repos/{owner}/{repo}/issues", params=params)
    issues = []
    for item in raw_list:
        if "pull_request" in item:       # GitHub returns PRs here too — skip them
            continue
        body = item.get("body") or ""
        issues.append({
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "labels": [lb["name"] for lb in item.get("labels", [])],
            "author": item["user"]["login"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "html_url": item["html_url"],
            "body_preview": body[:300] + ("…" if len(body) > 300 else ""),
        })
    return issues


# ---------------------------------------------------------------------------
# Tool: get_issue
# ---------------------------------------------------------------------------

@mcp.tool()
def get_issue(owner: str, repo: str, issue_number: int) -> dict:
    """
    Fetch full details for a single issue.

    Args:
        owner:        Repository owner.
        repo:         Repository name.
        issue_number: The issue number (not the internal ID).

    Returns a dict with all issue fields plus the full body text.
    """
    raw = _get(f"/repos/{owner}/{repo}/issues/{issue_number}")
    return {
        "number": raw["number"],
        "title": raw["title"],
        "state": raw["state"],
        "labels": [lb["name"] for lb in raw.get("labels", [])],
        "author": raw["user"]["login"],
        "assignees": [a["login"] for a in raw.get("assignees", [])],
        "comments": raw["comments"],
        "created_at": raw["created_at"],
        "updated_at": raw["updated_at"],
        "closed_at": raw.get("closed_at"),
        "html_url": raw["html_url"],
        "body": raw.get("body") or "",
    }


# ---------------------------------------------------------------------------
# Tool: create_issue
# ---------------------------------------------------------------------------

@mcp.tool()
def create_issue(
    owner: str,
    repo: str,
    title: str,
    body: str = "",
    labels: list[str] | None = None,
) -> dict:
    """
    Create a new issue in a repository.

    Args:
        owner:  Repository owner.
        repo:   Repository name.
        title:  Issue title (required).
        body:   Issue description in Markdown. Default empty.
        labels: List of label names to apply, e.g. ["bug", "help wanted"].

    Returns a dict with: number, title, html_url, created_at.
    """
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    raw = _post(f"/repos/{owner}/{repo}/issues", payload)
    return {
        "number": raw["number"],
        "title": raw["title"],
        "html_url": raw["html_url"],
        "created_at": raw["created_at"],
    }


# ---------------------------------------------------------------------------
# Tool: update_issue
# ---------------------------------------------------------------------------

@mcp.tool()
def update_issue(
    owner: str,
    repo: str,
    issue_number: int,
    title: str | None = None,
    body: str | None = None,
    state: str | None = None,
    labels: list[str] | None = None,
) -> dict:
    """
    Update an existing issue (edit title/body, open/close, change labels).

    Args:
        owner:        Repository owner.
        repo:         Repository name.
        issue_number: Issue number to update.
        title:        New title (optional).
        body:         New body text (optional).
        state:        "open" or "closed" (optional).
        labels:       Replacement label list (optional — replaces all existing labels).

    Returns the updated issue summary.
    """
    payload: dict = {}
    if title is not None:
        payload["title"] = title
    if body is not None:
        payload["body"] = body
    if state in ("open", "closed"):
        payload["state"] = state
    if labels is not None:
        payload["labels"] = labels

    raw = _patch(f"/repos/{owner}/{repo}/issues/{issue_number}", payload)
    return {
        "number": raw["number"],
        "title": raw["title"],
        "state": raw["state"],
        "html_url": raw["html_url"],
        "updated_at": raw["updated_at"],
    }


# ---------------------------------------------------------------------------
# Tool: list_pull_requests
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pull_requests(
    owner: str,
    repo: str,
    state: str = "open",
    per_page: int = 20,
) -> list[dict]:
    """
    List pull requests for a repository.

    Args:
        owner:    Repository owner.
        repo:     Repository name.
        state:    "open", "closed", or "all". Default "open".
        per_page: Number of PRs to return (1–50). Default 20.

    Returns a list of dicts with: number, title, state, author, base_branch,
    head_branch, draft, created_at, updated_at, html_url.
    """
    per_page = max(1, min(per_page, 50))
    raw_list = _get(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": state, "per_page": per_page},
    )
    prs = []
    for item in raw_list:
        prs.append({
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "author": item["user"]["login"],
            "base_branch": item["base"]["ref"],
            "head_branch": item["head"]["ref"],
            "draft": item.get("draft", False),
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "html_url": item["html_url"],
        })
    return prs


# ---------------------------------------------------------------------------
# Tool: get_pull_request
# ---------------------------------------------------------------------------

@mcp.tool()
def get_pull_request(owner: str, repo: str, pr_number: int) -> dict:
    """
    Fetch full details for a single pull request, including its diff stats.

    Args:
        owner:     Repository owner.
        repo:      Repository name.
        pr_number: Pull request number.

    Returns a dict with all PR fields, mergeable status, and changed-file stats.
    """
    raw = _get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
    return {
        "number": raw["number"],
        "title": raw["title"],
        "state": raw["state"],
        "author": raw["user"]["login"],
        "base_branch": raw["base"]["ref"],
        "head_branch": raw["head"]["ref"],
        "draft": raw.get("draft", False),
        "mergeable": raw.get("mergeable"),
        "mergeable_state": raw.get("mergeable_state"),
        "commits": raw.get("commits"),
        "additions": raw.get("additions"),
        "deletions": raw.get("deletions"),
        "changed_files": raw.get("changed_files"),
        "review_comments": raw.get("review_comments"),
        "body": raw.get("body") or "",
        "created_at": raw["created_at"],
        "updated_at": raw["updated_at"],
        "merged_at": raw.get("merged_at"),
        "html_url": raw["html_url"],
    }


# ---------------------------------------------------------------------------
# Tool: list_pr_files
# ---------------------------------------------------------------------------

@mcp.tool()
def list_pr_files(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    List all files changed in a pull request.

    Args:
        owner:     Repository owner.
        repo:      Repository name.
        pr_number: Pull request number.

    Returns a list of dicts with: filename, status, additions, deletions,
    changes, blob_url.
    """
    raw_list = _get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files")
    return [
        {
            "filename": f["filename"],
            "status": f["status"],          # added | removed | modified | renamed
            "additions": f["additions"],
            "deletions": f["deletions"],
            "changes": f["changes"],
            "blob_url": f.get("blob_url"),
        }
        for f in raw_list
    ]


# ---------------------------------------------------------------------------
# Tool: get_file_contents
# ---------------------------------------------------------------------------

@mcp.tool()
def get_file_contents(owner: str, repo: str, path: str, ref: str = "") -> dict:
    """
    Retrieve the decoded contents of a file from a repository.

    Args:
        owner: Repository owner.
        repo:  Repository name.
        path:  File path relative to the repo root, e.g. "src/main.py".
        ref:   Branch, tag, or commit SHA. Defaults to the repo's default branch.

    Returns a dict with: path, size, encoding, content (decoded UTF-8 text),
    sha, html_url.
    """
    import base64

    params: dict = {}
    if ref:
        params["ref"] = ref

    raw = _get(f"/repos/{owner}/{repo}/contents/{path}", params=params or None)
    if isinstance(raw, list):
        raise ValueError(f"'{path}' is a directory, not a file.")

    encoded = raw.get("content", "")
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        decoded = "[binary file — cannot decode as text]"

    return {
        "path": raw["path"],
        "size": raw["size"],
        "sha": raw["sha"],
        "content": decoded,
        "html_url": raw.get("html_url"),
    }


# ---------------------------------------------------------------------------
# Tool: list_repository_commits
# ---------------------------------------------------------------------------

@mcp.tool()
def list_repository_commits(
    owner: str,
    repo: str,
    branch: str = "",
    per_page: int = 20,
) -> list[dict]:
    """
    List recent commits on a branch (or the default branch).

    Args:
        owner:    Repository owner.
        repo:     Repository name.
        branch:   Branch name. Defaults to the repo's default branch.
        per_page: Number of commits to return (1–50). Default 20.

    Returns a list of dicts with: sha (short), message, author, date, html_url.
    """
    per_page = max(1, min(per_page, 50))
    params: dict = {"per_page": per_page}
    if branch:
        params["sha"] = branch

    raw_list = _get(f"/repos/{owner}/{repo}/commits", params=params)
    commits = []
    for item in raw_list:
        commit = item["commit"]
        commits.append({
            "sha": item["sha"][:7],
            "full_sha": item["sha"],
            "message": commit["message"].split("\n")[0],   # first line only
            "author": commit["author"]["name"],
            "date": commit["author"]["date"],
            "html_url": item["html_url"],
        })
    return commits


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the GitHub MCP server using stdio transport."""
    import sys

    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

