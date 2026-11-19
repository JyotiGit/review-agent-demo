"""Stores feedback records on a dedicated branch of the same repo (default: `review-feedback`).

Each accept / reject decision is saved as its own JSON file, so records are never overwritten
and two decisions at the same moment can't conflict:

    feedback/2026/11/19/20261119T103012345678Z-pr2-c1234567-accepted.json

The branch is created automatically the first time a decision is stored. To swap in a database
later, replace this class - nothing else needs to change.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

from .github_client import GitHubClient

DEFAULT_BRANCH = "review-feedback"


class FeedbackStore:
    def __init__(self, gh: GitHubClient, branch: str = DEFAULT_BRANCH):
        self.gh = gh
        self.branch = branch

    def _ensure_branch(self) -> None:
        repo = self.gh.repo
        r = self.gh.request("GET", f"/repos/{repo}/git/ref/heads/{self.branch}")
        if r.status_code != 404:
            r.raise_for_status()
            return
        # Create an empty branch (no shared history with main) holding just a README.
        tree = self.gh.request("POST", f"/repos/{repo}/git/trees", json={"tree": [{
            "path": "README.md", "mode": "100644", "type": "blob",
            "content": "# AI review feedback\n\nAccept / reject decisions on AI review comments, written "
                       "automatically by the review agent. One JSON file per decision under `feedback/`.\n"
                       "Do not merge this branch.\n",
        }]})
        tree.raise_for_status()
        commit = self.gh.request("POST", f"/repos/{repo}/git/commits", json={
            "message": "Create feedback store", "tree": tree.json()["sha"], "parents": [],
        })
        commit.raise_for_status()
        ref = self.gh.request("POST", f"/repos/{repo}/git/refs", json={
            "ref": f"refs/heads/{self.branch}", "sha": commit.json()["sha"],
        })
        if ref.status_code not in (201, 422):  # 422 = created by another run a moment ago
            ref.raise_for_status()

    def save(self, record: dict) -> str:
        """Writes one feedback record. Returns its path on the branch."""
        self._ensure_branch()
        now = datetime.now(timezone.utc)
        record = {"recorded_at": now.isoformat(), "repo": self.gh.repo, **record}
        path = (f"feedback/{now:%Y/%m/%d}/{now:%Y%m%dT%H%M%S%f}Z-"
                f"pr{record.get('pr_number')}-c{record.get('comment_id')}-{record.get('decision')}.json")
        r = self.gh.request("PUT", f"/repos/{self.gh.repo}/contents/{path}", json={
            "message": f"feedback: PR #{record.get('pr_number')} comment {record.get('comment_id')} "
                       f"{record.get('decision')} by @{record.get('decided_by')}",
            "branch": self.branch,
            "content": base64.b64encode(json.dumps(record, indent=2, ensure_ascii=False).encode()).decode(),
        })
        r.raise_for_status()
        return path
