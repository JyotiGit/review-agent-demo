"""Minimal GitHub REST API client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import requests

API = "https://api.github.com"
NULL_SHA = "0" * 40


@dataclass
class ChangedFile:
    filename: str
    status: str          # added / modified / removed / renamed
    additions: int
    deletions: int
    patch: str | None    # unified diff; None for binary or very large files


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.repo = repo  # "owner/name"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    # ---- low-level helpers -------------------------------------------------
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API}{path}"
        return self.session.request(method, url, timeout=30, **kwargs)

    def get(self, path: str, **kwargs):
        r = self.request("GET", path, **kwargs)
        r.raise_for_status()
        return r.json()

    def paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        params = {"per_page": 100, **(params or {})}
        url: str | None = path
        while url:
            r = self.request("GET", url, params=params)
            r.raise_for_status()
            yield from r.json()
            url = r.links.get("next", {}).get("url")
            params = None  # the "next" URL already carries the query string

    # ---- push diffs --------------------------------------------------------
    def get_push_changes(self, before: str, after: str) -> list[ChangedFile]:
        """Files changed by a push. For a new branch (before == 000..0), use the head commit only."""
        if not before or before == NULL_SHA:
            data = self.get(f"/repos/{self.repo}/commits/{after}")
        else:
            data = self.get(f"/repos/{self.repo}/compare/{before}...{after}")
        return [
            ChangedFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch"),
            )
            for f in data.get("files", [])
        ]

    # ---- commit comments ---------------------------------------------------
    def post_commit_comment(self, sha: str, body: str) -> dict:
        r = self.request("POST", f"/repos/{self.repo}/commits/{sha}/comments", json={"body": body})
        r.raise_for_status()
        return r.json()

    def list_commit_comments_for_sha(self, sha: str) -> list[dict]:
        return list(self.paginate(f"/repos/{self.repo}/commits/{sha}/comments"))

    def list_all_commit_comments(self) -> Iterator[dict]:
        return self.paginate(f"/repos/{self.repo}/comments")

    def list_comment_reactions(self, comment_id: int) -> list[dict]:
        return list(self.paginate(f"/repos/{self.repo}/comments/{comment_id}/reactions"))
