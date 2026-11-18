"""Shared helpers: recognising review comments, summarising them, parsing user actions."""
from __future__ import annotations

import re

HEADER = "## 🤖 AI Code Review"

# Commands a developer can type in a reply on the commit to tell the agent what they did.
COMMANDS = {
    "/accept": "accepted",
    "/reject": "rejected",
    "/fixed": "fixed",
    "/false-positive": "false_positive",
    "/wontfix": "wont_fix",
}

REACTION_MEANING = {
    "+1": "helpful", "-1": "not_helpful", "heart": "helpful", "hooray": "helpful",
    "rocket": "helpful", "confused": "unclear", "laugh": "other", "eyes": "seen",
}


def is_review_comment(comment: dict) -> bool:
    return (comment.get("body") or "").startswith(HEADER)


def is_bot(user: dict | None) -> bool:
    user = user or {}
    return user.get("type") == "Bot" or user.get("login", "").endswith("[bot]")


def summarize_review(body: str) -> dict:
    """Pull rough stats out of the review text: issue counts by severity and the verdict."""
    issues = body.split("**Suggestions**")[0]
    verdict_part = body.split("**Verdict**")[-1] if "**Verdict**" in body else body
    if "❌" in verdict_part:
        verdict = "significant_changes"
    elif "⚠️" in verdict_part:
        verdict = "minor_changes"
    elif "✅" in verdict_part:
        verdict = "looks_good"
    else:
        verdict = "unknown"
    return {
        "issues_high": issues.count("🔴"),
        "issues_medium": issues.count("🟠"),
        "issues_low": issues.count("🟡"),
        "verdict": verdict,
    }


def parse_action(body: str) -> str:
    """Return the first command found in a reply, or 'replied' for a plain comment."""
    for word in re.findall(r"/[a-z-]+", (body or "").lower()):
        if word in COMMANDS:
            return COMMANDS[word]
    return "replied"
