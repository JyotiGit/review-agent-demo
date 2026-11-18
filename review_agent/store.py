"""Event log stored in a dedicated branch of the same repo (default: `review-logs`).

Each event is its own small JSON file, so concurrent workflow runs never conflict:
    events/2026/11/13/20261113T071500123456Z-review_posted-1a2b3c4d.json

Mutable state (e.g. the last-seen reactions on a review) lives under `state/`.
Swap this class for a database-backed one later without touching the rest of the agent.
"""
from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timezone

from .github_client import GitHubClient

DEFAULT_BRANCH = "review-logs"


class LogStore:
    def __init__(self, gh: GitHubClient, branch: str = DEFAULT_BRANCH):
        self.gh = gh
        self.branch = branch
        self._ready = False

    # ---- branch bootstrap --------------------------------------------------
    def ensure_branch(self) -> None:
        if self._ready:
            return
        repo = self.gh.repo
        r = self.gh.request("GET", f"/repos/{repo}/git/ref/heads/{self.branch}")
        if r.status_code == 404:
            tree = self.gh.request("POST", f"/repos/{repo}/git/trees", json={"tree": [{
                "path": "README.md", "mode": "100644", "type": "blob",
                "content": "# Review logs\n\nWritten automatically by the AI code review agent. "
                           "Do not merge this branch.\n",
            }]})
            tree.raise_for_status()
            commit = self.gh.request("POST", f"/repos/{repo}/git/commits", json={
                "message": "Initialise review log", "tree": tree.json()["sha"], "parents": [],
            })
            commit.raise_for_status()
            ref = self.gh.request("POST", f"/repos/{repo}/git/refs", json={
                "ref": f"refs/heads/{self.branch}", "sha": commit.json()["sha"],
            })
            if ref.status_code not in (201, 422):  # 422 = another run created it first
                ref.raise_for_status()
        else:
            r.raise_for_status()
        self._ready = True

    # ---- files -------------------------------------------------------------
    def read_json(self, path: str) -> tuple[dict | list | None, str | None]:
        """Returns (data, blob_sha) or (None, None) if the file doesn't exist."""
        self.ensure_branch()
        r = self.gh.request("GET", f"/repos/{self.gh.repo}/contents/{path}", params={"ref": self.branch})
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        meta = r.json()
        return json.loads(base64.b64decode(meta["content"])), meta["sha"]

    def list_dir(self, path: str) -> list[dict]:
        self.ensure_branch()
        r = self.gh.request("GET", f"/repos/{self.gh.repo}/contents/{path}", params={"ref": self.branch})
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()

    def write_json(self, path: str, data, message: str, sha: str | None = None) -> None:
        self.ensure_branch()
        payload = {
            "message": message,
            "branch": self.branch,
            "content": base64.b64encode(json.dumps(data, indent=2, ensure_ascii=False).encode()).decode(),
        }
        if sha:
            payload["sha"] = sha
        r = self.gh.request("PUT", f"/repos/{self.gh.repo}/contents/{path}", json=payload)
        r.raise_for_status()

    def delete_file(self, path: str, sha: str, message: str) -> None:
        r = self.gh.request("DELETE", f"/repos/{self.gh.repo}/contents/{path}",
                            json={"message": message, "sha": sha, "branch": self.branch})
        r.raise_for_status()

    # ---- events ------------------------------------------------------------
    def record(self, event_type: str, **data) -> dict:
        now = datetime.now(timezone.utc)
        event = {"type": event_type, "timestamp": now.isoformat(), "repo": self.gh.repo, **data}
        path = (f"events/{now:%Y/%m/%d}/{now:%Y%m%dT%H%M%S%f}Z-"
                f"{event_type}-{uuid.uuid4().hex[:8]}.json")
        self.write_json(path, event, f"log: {event_type}")
        print(f"Logged {event_type} -> {self.branch}:{path}")
        return event

    # ---- reaction snapshots (used to detect changes between syncs) --------
    def reaction_snapshot_path(self, comment_id: int) -> str:
        return f"state/reactions/{comment_id}.json"
