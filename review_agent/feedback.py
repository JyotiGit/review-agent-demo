"""Records a developer's reply on a reviewed commit (runs on the `commit_comment` event).

    python -m review_agent.feedback
"""
from __future__ import annotations

import os
import sys

from .events import is_bot, is_review_comment, parse_action
from .github_client import GitHubClient
from .main import load_event
from .store import LogStore


def main() -> int:
    event = load_event()
    comment = event.get("comment") or {}
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    if not (comment and repo and token):
        print("Not a commit_comment event.", file=sys.stderr)
        return 1
    if is_bot(comment.get("user")) or is_review_comment(comment):
        print("Comment is from a bot or is a review itself - ignoring.")
        return 0

    gh = GitHubClient(token, repo)
    sha = comment["commit_id"]

    # Link the reply to the most recent AI review on the same commit, posted before it.
    reviews = [c for c in gh.list_commit_comments_for_sha(sha)
               if is_review_comment(c) and c["created_at"] <= comment["created_at"]]
    review = max(reviews, key=lambda c: c["created_at"], default=None)
    if review is None:
        print("No AI review on this commit - nothing to record.")
        return 0

    LogStore(gh).record(
        "user_reply",
        review_comment_id=review["id"],
        comment_id=comment["id"],
        comment_url=comment.get("html_url"),
        commit_sha=sha,
        user=comment["user"]["login"],
        action=parse_action(comment.get("body", "")),
        file=comment.get("path"),
        line=comment.get("line"),
        body=comment.get("body", ""),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
