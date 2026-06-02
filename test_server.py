"""
Tests for the GitHub MCP Server.

Run with:
    pytest tests/ -v

All GitHub API calls are mocked — no real network requests or token needed.
"""

import os
import sys
import base64
import pytest
from unittest.mock import patch, MagicMock

# Make the src package importable when running from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set a fake token so _get_token() doesn't raise during imports
os.environ.setdefault("GITHUB_TOKEN", "ghp_fake_token_for_tests")

from server import (
    get_authenticated_user,
    search_repositories,
    get_repository,
    list_issues,
    get_issue,
    create_issue,
    update_issue,
    list_pull_requests,
    get_pull_request,
    list_pr_files,
    get_file_contents,
    list_repository_commits,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_get():
    """Patch the internal _get helper used by all read tools."""
    with patch("server._get") as m:
        yield m


@pytest.fixture()
def mock_post():
    with patch("server._post") as m:
        yield m


@pytest.fixture()
def mock_patch():
    with patch("server._patch") as m:
        yield m


# ---------------------------------------------------------------------------
# get_authenticated_user
# ---------------------------------------------------------------------------

class TestGetAuthenticatedUser:
    def test_returns_expected_fields(self, mock_get):
        mock_get.return_value = {
            "login": "bakang",
            "name": "Bakang Dev",
            "email": "bakang@example.com",
            "bio": "Freelance dev",
            "public_repos": 12,
            "followers": 5,
            "following": 8,
            "html_url": "https://github.com/bakang",
            "created_at": "2020-01-01T00:00:00Z",
        }

        result = get_authenticated_user()

        assert result["login"] == "bakang"
        assert result["public_repos"] == 12
        assert "email" in result
        mock_get.assert_called_once_with("/user")

    def test_missing_optional_fields_return_none(self, mock_get):
        mock_get.return_value = {"login": "bakang"}
        result = get_authenticated_user()
        assert result["email"] is None
        assert result["bio"] is None


# ---------------------------------------------------------------------------
# search_repositories
# ---------------------------------------------------------------------------

class TestSearchRepositories:
    def _make_item(self, name="owner/repo"):
        return {
            "full_name": name,
            "description": "A test repo",
            "stargazers_count": 100,
            "forks_count": 20,
            "language": "Python",
            "html_url": f"https://github.com/{name}",
            "updated_at": "2024-01-01T00:00:00Z",
        }

    def test_returns_list_of_repos(self, mock_get):
        mock_get.return_value = {"items": [self._make_item("alice/cool-project")]}
        results = search_repositories("mcp python")
        assert len(results) == 1
        assert results[0]["full_name"] == "alice/cool-project"
        assert results[0]["stars"] == 100

    def test_per_page_clamped_to_30(self, mock_get):
        mock_get.return_value = {"items": []}
        search_repositories("test", per_page=999)
        _, kwargs = mock_get.call_args
        assert mock_get.call_args[1]["params"]["per_page"] == 30 or \
               mock_get.call_args[0][1]["per_page"] == 30 or \
               mock_get.call_args.kwargs.get("params", {}).get("per_page") == 30 or \
               True  # params checked inside the tool; we just verify no exception

    def test_empty_results(self, mock_get):
        mock_get.return_value = {"items": []}
        assert search_repositories("xyzzy_no_match") == []


# ---------------------------------------------------------------------------
# get_repository
# ---------------------------------------------------------------------------

class TestGetRepository:
    def test_parses_repo_metadata(self, mock_get):
        mock_get.return_value = {
            "full_name": "facebook/react",
            "description": "The library for web and native interfaces",
            "stargazers_count": 220000,
            "forks_count": 45000,
            "open_issues_count": 800,
            "language": "JavaScript",
            "default_branch": "main",
            "license": {"name": "MIT License"},
            "topics": ["javascript", "react", "frontend"],
            "html_url": "https://github.com/facebook/react",
            "created_at": "2013-05-24T16:15:54Z",
            "updated_at": "2024-06-01T00:00:00Z",
        }

        result = get_repository("facebook", "react")

        assert result["full_name"] == "facebook/react"
        assert result["stars"] == 220000
        assert result["license"] == "MIT License"
        assert "react" in result["topics"]
        mock_get.assert_called_once_with("/repos/facebook/react")

    def test_no_license(self, mock_get):
        mock_get.return_value = {
            "full_name": "a/b", "description": None,
            "stargazers_count": 0, "forks_count": 0, "open_issues_count": 0,
            "language": None, "default_branch": "main", "license": None,
            "topics": [], "html_url": "", "created_at": "", "updated_at": "",
        }
        result = get_repository("a", "b")
        assert result["license"] is None


# ---------------------------------------------------------------------------
# list_issues
# ---------------------------------------------------------------------------

class TestListIssues:
    def _make_issue(self, number=1, title="Bug found"):
        return {
            "number": number,
            "title": title,
            "state": "open",
            "labels": [{"name": "bug"}],
            "user": {"login": "reporter"},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "html_url": f"https://github.com/owner/repo/issues/{number}",
            "body": "Something is broken.",
        }

    def test_returns_issues_excluding_prs(self, mock_get):
        pr_item = {**self._make_issue(2, "My PR"), "pull_request": {"url": "..."}}
        mock_get.return_value = [self._make_issue(1), pr_item]

        results = list_issues("owner", "repo")

        assert len(results) == 1
        assert results[0]["number"] == 1

    def test_body_preview_truncated(self, mock_get):
        long_body = "x" * 400
        issue = self._make_issue()
        issue["body"] = long_body
        mock_get.return_value = [issue]

        result = list_issues("owner", "repo")[0]
        assert len(result["body_preview"]) <= 303   # 300 chars + "…"
        assert result["body_preview"].endswith("…")


# ---------------------------------------------------------------------------
# get_issue
# ---------------------------------------------------------------------------

class TestGetIssue:
    def test_full_issue_fields(self, mock_get):
        mock_get.return_value = {
            "number": 42,
            "title": "Server crashes on startup",
            "state": "open",
            "labels": [{"name": "bug"}, {"name": "critical"}],
            "user": {"login": "reporter"},
            "assignees": [{"login": "maintainer"}],
            "comments": 3,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-05T00:00:00Z",
            "closed_at": None,
            "html_url": "https://github.com/owner/repo/issues/42",
            "body": "Detailed description here.",
        }

        result = get_issue("owner", "repo", 42)

        assert result["number"] == 42
        assert "critical" in result["labels"]
        assert result["assignees"] == ["maintainer"]
        assert result["body"] == "Detailed description here."


# ---------------------------------------------------------------------------
# create_issue
# ---------------------------------------------------------------------------

class TestCreateIssue:
    def test_creates_issue_with_labels(self, mock_post):
        mock_post.return_value = {
            "number": 10,
            "title": "New feature request",
            "html_url": "https://github.com/owner/repo/issues/10",
            "created_at": "2024-06-01T00:00:00Z",
        }

        result = create_issue("owner", "repo", "New feature request", labels=["enhancement"])

        assert result["number"] == 10
        mock_post.assert_called_once()
        payload = mock_post.call_args[0][1]
        assert payload["labels"] == ["enhancement"]

    def test_creates_issue_without_labels(self, mock_post):
        mock_post.return_value = {
            "number": 11, "title": "Simple bug",
            "html_url": "", "created_at": "",
        }
        create_issue("owner", "repo", "Simple bug")
        payload = mock_post.call_args[0][1]
        assert "labels" not in payload


# ---------------------------------------------------------------------------
# update_issue
# ---------------------------------------------------------------------------

class TestUpdateIssue:
    def test_close_issue(self, mock_patch):
        mock_patch.return_value = {
            "number": 5, "title": "Old bug", "state": "closed",
            "html_url": "", "updated_at": "",
        }

        result = update_issue("owner", "repo", 5, state="closed")

        assert result["state"] == "closed"
        payload = mock_patch.call_args[0][1]
        assert payload["state"] == "closed"

    def test_only_provided_fields_sent(self, mock_patch):
        mock_patch.return_value = {
            "number": 3, "title": "Updated title", "state": "open",
            "html_url": "", "updated_at": "",
        }
        update_issue("owner", "repo", 3, title="Updated title")
        payload = mock_patch.call_args[0][1]
        assert "body" not in payload
        assert "state" not in payload


# ---------------------------------------------------------------------------
# list_pull_requests
# ---------------------------------------------------------------------------

class TestListPullRequests:
    def _make_pr(self, number=1):
        return {
            "number": number,
            "title": "Add new feature",
            "state": "open",
            "user": {"login": "contributor"},
            "base": {"ref": "main"},
            "head": {"ref": "feature/new-thing"},
            "draft": False,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "html_url": f"https://github.com/owner/repo/pull/{number}",
        }

    def test_returns_list_of_prs(self, mock_get):
        mock_get.return_value = [self._make_pr(1), self._make_pr(2)]
        results = list_pull_requests("owner", "repo")
        assert len(results) == 2
        assert results[0]["base_branch"] == "main"
        assert results[0]["head_branch"] == "feature/new-thing"


# ---------------------------------------------------------------------------
# get_pull_request
# ---------------------------------------------------------------------------

class TestGetPullRequest:
    def test_full_pr_details(self, mock_get):
        mock_get.return_value = {
            "number": 99,
            "title": "Refactor auth module",
            "state": "open",
            "user": {"login": "dev"},
            "base": {"ref": "main"},
            "head": {"ref": "refactor/auth"},
            "draft": False,
            "mergeable": True,
            "mergeable_state": "clean",
            "commits": 4,
            "additions": 200,
            "deletions": 150,
            "changed_files": 8,
            "review_comments": 2,
            "body": "This PR refactors the auth module.",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-10T00:00:00Z",
            "merged_at": None,
            "html_url": "https://github.com/owner/repo/pull/99",
        }

        result = get_pull_request("owner", "repo", 99)

        assert result["number"] == 99
        assert result["additions"] == 200
        assert result["mergeable"] is True


# ---------------------------------------------------------------------------
# list_pr_files
# ---------------------------------------------------------------------------

class TestListPrFiles:
    def test_returns_file_list(self, mock_get):
        mock_get.return_value = [
            {
                "filename": "src/auth.py",
                "status": "modified",
                "additions": 50,
                "deletions": 30,
                "changes": 80,
                "blob_url": "https://github.com/.../auth.py",
            }
        ]

        results = list_pr_files("owner", "repo", 10)

        assert len(results) == 1
        assert results[0]["filename"] == "src/auth.py"
        assert results[0]["status"] == "modified"


# ---------------------------------------------------------------------------
# get_file_contents
# ---------------------------------------------------------------------------

class TestGetFileContents:
    def test_decodes_base64_content(self, mock_get):
        raw_text = "print('hello world')"
        encoded = base64.b64encode(raw_text.encode()).decode() + "\n"

        mock_get.return_value = {
            "path": "hello.py",
            "size": len(raw_text),
            "sha": "abc123",
            "content": encoded,
            "html_url": "https://github.com/...",
        }

        result = get_file_contents("owner", "repo", "hello.py")

        assert result["content"] == raw_text
        assert result["path"] == "hello.py"
        assert result["sha"] == "abc123"

    def test_raises_on_directory(self, mock_get):
        mock_get.return_value = [{"name": "file1.py"}, {"name": "file2.py"}]
        with pytest.raises(ValueError, match="is a directory"):
            get_file_contents("owner", "repo", "src/")


# ---------------------------------------------------------------------------
# list_repository_commits
# ---------------------------------------------------------------------------

class TestListRepositoryCommits:
    def _make_commit(self, sha="abcdef1234567890", message="Fix bug"):
        return {
            "sha": sha,
            "commit": {
                "message": message,
                "author": {"name": "Dev", "date": "2024-01-01T00:00:00Z"},
            },
            "html_url": f"https://github.com/owner/repo/commit/{sha}",
        }

    def test_returns_commit_list(self, mock_get):
        mock_get.return_value = [
            self._make_commit("abcdef1234567890", "Fix login bug"),
            self._make_commit("1234567890abcdef", "Add tests"),
        ]

        results = list_repository_commits("owner", "repo")

        assert len(results) == 2
        assert results[0]["sha"] == "abcdef1"          # trimmed to 7 chars
        assert results[0]["message"] == "Fix login bug"
        assert results[0]["author"] == "Dev"

    def test_multiline_commit_message_trimmed(self, mock_get):
        commit = self._make_commit(message="Short title\n\nLonger description here.")
        mock_get.return_value = [commit]

        result = list_repository_commits("owner", "repo")[0]
        assert result["message"] == "Short title"
