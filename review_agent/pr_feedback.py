"""Handles `/accept` and `/reject` replies to an AI review comment.

Runs on the `pull_request_review_comment` event (a reply in a comment thread on the PR):
    python -m review_agent.pr_feedback
"""
from __future__ import annotations

import os
import sys

from .comments import COMMENT_MARKER, parse_ai_comment, parse_decision, with_decision
from .github_client import GitHubClient
from .pr_review import load_event
from .store import FeedbackStore


def main() -> int:
    event = load_event()
    reply = event.get("comment") or {}
    repo = os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    parent_id = reply.get("in_reply_to_id")
    if not (reply and parent_id and repo and token):
        print("Not a reply in a review comment thread - ignoring.")
        return 0

    decision = parse_decision(reply.get("body", ""))
    if decision is None:
        print("Reply is not /accept or /reject - ignoring.")
        return 0
    action, reason = decision
    user = reply["user"]["login"]

    gh = GitHubClient(token, repo)
    parent = gh.get_review_comment(parent_id)
    if COMMENT_MARKER not in (parent.get("body") or ""):
        print("The comment being replied to isn't an AI review comment - ignoring.")
        return 0

    gh.update_review_comment(parent_id, with_decision(parent["body"], action, user, reason))
    gh.add_review_comment_reaction(reply["id"], "+1")
    print(f"@{user} {action} comment {parent_id}" + (f": {reason}" if reason else ""))

    # Store a permanent record of the decision.
    pr = event.get("pull_request") or {}
    ai = parse_ai_comment(parent["body"])  # severity, category and text of the AI comment
    record = {
        "pr_number": pr.get("number"),
        "pr_title": pr.get("title"),
        "pr_author": (pr.get("user") or {}).get("login"),
        "comment_id": parent_id,
        "comment_url": parent.get("html_url"),
        "commit_sha": parent.get("commit_id"),
        "file": parent.get("path"),
        "line": parent.get("line") or parent.get("original_line"),
        "severity": ai["severity"],
        "category": ai["category"],
        "comment": ai["comment"],
        "comment_created_at": parent.get("created_at"),
        "decision": action,
        "decided_by": user,
        "reason": reason,
        "decided_at": reply.get("created_at"),
        "reply_id": reply["id"],
        "reply_url": reply.get("html_url"),
    }
    try:
        path = FeedbackStore(gh).save(record)
    except Exception as exc:  # noqa: BLE001
        print(f"::error::Decision shown on the PR but could not be stored: {exc}")
        return 1
    print(f"Stored on branch '{FeedbackStore(gh).branch}': {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
