"""Entry point: review a push and record it.

In GitHub Actions it reads the push event automatically:
    python -m review_agent.main

Locally (to test against any commit you have access to):
    python -m review_agent.main --repo owner/name --sha <commit_sha> [--before <sha>] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .events import HEADER, summarize_review
from .github_client import NULL_SHA, GitHubClient
from .reviewer import DEFAULT_MODEL, review_changes
from .store import LogStore


def load_event() -> dict:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    p = argparse.ArgumentParser(description="AI code review for a GitHub push")
    p.add_argument("--repo", help="owner/name (default: $GITHUB_REPOSITORY)")
    p.add_argument("--sha", help="head commit SHA (default: from push event)")
    p.add_argument("--before", help="previous SHA (default: from push event)")
    p.add_argument("--dry-run", action="store_true", help="print the review instead of posting or logging it")
    args = p.parse_args()

    event = load_event()
    repo = args.repo or os.getenv("GITHUB_REPOSITORY")
    after = args.sha or event.get("after")
    before = args.before or event.get("before") or NULL_SHA
    commit_message = (event.get("head_commit") or {}).get("message", "")
    token = os.getenv("GITHUB_TOKEN")

    if not (repo and after and token):
        print("Missing repo, commit SHA or GITHUB_TOKEN.", file=sys.stderr)
        return 1
    if event.get("deleted"):
        print("Branch deleted - nothing to review.")
        return 0

    gh = GitHubClient(token, repo)
    files = gh.get_push_changes(before, after)
    print(f"Reviewing {len(files)} changed file(s) in {repo} @ {after[:7]}")

    review = review_changes(files, commit_message)
    if review is None:
        print("No reviewable changes.")
        return 0

    body = f"{HEADER}\n\n{review}\n\n---\n<sub>Reply with `/accept`, `/reject`, `/fixed`, " \
           f"`/false-positive` or `/wontfix`, or react 👍 / 👎 to rate this review.</sub>"

    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(body + "\n")

    if args.dry_run:
        print(body)
        return 0

    comment = gh.post_commit_comment(after, body)
    print(f"Review posted: {comment.get('html_url')}")

    # Record the review. A logging failure should never hide the review itself.
    try:
        store = LogStore(gh)
        store.record(
            "review_posted",
            review_comment_id=comment["id"],
            review_url=comment.get("html_url"),
            commit_sha=after,
            branch=(event.get("ref") or "").removeprefix("refs/heads/"),
            pusher=(event.get("pusher") or {}).get("name"),
            commit_message=commit_message,
            files_changed=[f.filename for f in files],
            model=os.getenv("REVIEW_MODEL", DEFAULT_MODEL),
            body=body,
            **summarize_review(review),
        )
        store.write_json(store.reaction_snapshot_path(comment["id"]),
                         {"commit_sha": after, "reactions": []}, "state: new review")
    except Exception as exc:  # noqa: BLE001
        print(f"::warning::Review posted but could not be logged: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
