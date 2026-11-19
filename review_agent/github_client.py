"""Minimal GitHub REST API client for pull request reviews."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import requests

API = "https://api.github.com"


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

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("http") else f"{API}{path}"
        return self.session.request(method, url, timeout=30, **kwargs)

    def get(self, path: str, **kwargs):
        r = self.request("GET", path, **kwargs)
        r.raise_for_status()
        return r.json()

    def paginate(self, path: str) -> Iterator[dict]:
        url: str | None = path
        params: dict | None = {"per_page": 100}
        while url:
            r = self.request("GET", url, params=params)
            r.raise_for_status()
            yield from r.json()
            url = r.links.get("next", {}).get("url")
            params = None  # the "next" URL already carries the query string

    def get_pull_request(self, number: int) -> dict:
        return self.get(f"/repos/{self.repo}/pulls/{number}")

    def get_pr_files(self, number: int) -> list[ChangedFile]:
        return [
            ChangedFile(
                filename=f["filename"],
                status=f["status"],
                additions=f.get("additions", 0),
                deletions=f.get("deletions", 0),
                patch=f.get("patch"),
            )
            for f in self.paginate(f"/repos/{self.repo}/pulls/{number}/files")
        ]

    def post_pr_review(self, number: int, commit_sha: str, body: str, comments: list[dict]) -> dict:
        """Posts one PR review: a summary plus inline comments on specific lines."""
        r = self.request("POST", f"/repos/{self.repo}/pulls/{number}/reviews",
                         json={"commit_id": commit_sha, "body": body, "event": "COMMENT", "comments": comments})
        r.raise_for_status()
        return r.json()

    # ---- reporting ---------------------------------------------------------
    def list_pulls(self) -> Iterator[dict]:
        """Every PR in the repo, open and closed."""
        return self.paginate(f"/repos/{self.repo}/pulls?state=all")

    def list_all_review_comments(self) -> Iterator[dict]:
        """Every inline review comment on every PR (includes reaction counts)."""
        return self.paginate(f"/repos/{self.repo}/pulls/comments")

    # ---- inline review comments (accept / reject) -------------------------
    def get_review_comment(self, comment_id: int) -> dict:
        return self.get(f"/repos/{self.repo}/pulls/comments/{comment_id}")

    def update_review_comment(self, comment_id: int, body: str) -> dict:
        r = self.request("PATCH", f"/repos/{self.repo}/pulls/comments/{comment_id}", json={"body": body})
        r.raise_for_status()
        return r.json()

    def add_review_comment_reaction(self, comment_id: int, content: str) -> None:
        r = self.request("POST", f"/repos/{self.repo}/pulls/comments/{comment_id}/reactions",
                         json={"content": content})
        r.raise_for_status()
