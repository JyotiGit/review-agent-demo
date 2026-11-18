"""Records reactions (👍 👎 …) on review comments, and reviews that were deleted.

GitHub doesn't trigger workflows on reactions, so this runs on a schedule and compares
each review's current reactions with the snapshot saved last time.

    python -m review_agent.sync
"""
from __future__ import annotations

import os
import sys

from .events import REACTION_MEANING, is_bot, is_review_comment
from .github_client import GitHubClient
from .store import LogStore

REACTION_KEYS = ["+1", "-1", "laugh", "hooray", "confused", "heart", "rocket", "eyes"]


def main() -> int:
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    if not (repo and token):
        print("Missing GITHUB_REPOSITORY or GITHUB_TOKEN.", file=sys.stderr)
        return 1

    gh = GitHubClient(token, repo)
    store = LogStore(gh)
    seen: set[int] = set()
    changes = 0

    for comment in gh.list_all_commit_comments():
        if not (is_review_comment(comment) and is_bot(comment.get("user"))):
            continue
        cid = comment["id"]
        seen.add(cid)
        path = store.reaction_snapshot_path(cid)
        snapshot, sha = store.read_json(path)
        snapshot = snapshot or {"commit_sha": comment["commit_id"], "reactions": []}

        # Cheap check first: compare per-type counts before fetching who reacted.
        counts = {k: (comment.get("reactions") or {}).get(k, 0) for k in REACTION_KEYS}
        old_counts = {k: 0 for k in REACTION_KEYS}
        for r in snapshot["reactions"]:
            old_counts[r["content"]] = old_counts.get(r["content"], 0) + 1
        if counts == old_counts and sha:
            continue

        current = [{"user": r["user"]["login"], "content": r["content"], "created_at": r["created_at"]}
                   for r in gh.list_comment_reactions(cid)]
        now_keys = {(r["user"], r["content"]) for r in current}
        old_keys = {(r["user"], r["content"]) for r in snapshot["reactions"]}

        for user, content in sorted(now_keys - old_keys):
            store.record("reaction_added", review_comment_id=cid, commit_sha=comment["commit_id"],
                         user=user, reaction=content, meaning=REACTION_MEANING.get(content, "other"))
            changes += 1
        for user, content in sorted(old_keys - now_keys):
            store.record("reaction_removed", review_comment_id=cid, commit_sha=comment["commit_id"],
                         user=user, reaction=content, meaning=REACTION_MEANING.get(content, "other"))
            changes += 1

        store.write_json(path, {"commit_sha": comment["commit_id"], "reactions": current},
                         "state: reactions", sha=sha)

    # Reviews we were tracking that no longer exist were deleted by someone.
    for entry in store.list_dir("state/reactions"):
        cid = int(entry["name"].removesuffix(".json"))
        if cid not in seen:
            snapshot, _ = store.read_json(entry["path"])
            store.record("review_deleted", review_comment_id=cid,
                         commit_sha=(snapshot or {}).get("commit_sha"))
            store.delete_file(entry["path"], entry["sha"], "state: review deleted")
            changes += 1

    print(f"Sync complete: {len(seen)} review(s) checked, {changes} change(s) recorded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
