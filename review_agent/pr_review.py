"""Entry point: review a pull request and post the feedback on it.

In GitHub Actions it reads the pull_request event automatically:
    python -m review_agent.pr_review

Locally (to test against any PR you have access to):
    python -m review_agent.pr_review --repo owner/name --pr 1 [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .github_client import GitHubClient
from .reviewer import review_changes

HEADER = "## 🤖 AI Code Review"


def load_event() -> dict:
    path = os.getenv("GITHUB_EVENT_PATH")
    if not path:
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    p = argparse.ArgumentParser(description="AI code review for a GitHub pull request")
    p.add_argument("--repo", help="owner/name (default: $GITHUB_REPOSITORY)")
    p.add_argument("--pr", type=int, help="pull request number (default: from the event)")
    p.add_argument("--dry-run", action="store_true", help="print the review instead of posting it")
    args = p.parse_args()

    event = load_event()
    repo = args.repo or os.getenv("GITHUB_REPOSITORY")
    token = os.getenv("GITHUB_TOKEN")
    number = args.pr or (event.get("pull_request") or {}).get("number")

    if not (repo and token and number):
        print("Missing repo, PR number or GITHUB_TOKEN.", file=sys.stderr)
        return 1
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("::error::ANTHROPIC_API_KEY is not set. Add it under Settings → Secrets and variables → Actions.")
        return 1

    gh = GitHubClient(token, repo)
    pr = gh.get_pull_request(number)
    if pr.get("draft"):
        print("Draft PR - skipping until it's marked ready for review.")
        return 0

    files = gh.get_pr_files(number)
    print(f"Reviewing PR #{number} '{pr['title']}' ({len(files)} changed file(s)) in {repo}")

    review = review_changes(files, pr.get("title", ""), pr.get("body") or "")
    if review is None:
        print("No reviewable changes.")
        return 0

    head_sha = pr["head"]["sha"]
    body = f"{HEADER}\n\n{review}\n\n---\n<sub>Reviewed commit `{head_sha[:7]}`</sub>"

    # Show the review on the Actions run page too
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(body + "\n")

    if args.dry_run:
        print(body)
        return 0

    result = gh.post_pr_review(number, head_sha, body)
    print(f"Review posted: {result.get('html_url')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
