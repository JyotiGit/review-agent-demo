"""The review 'brain': turns a set of diffs into a review using Claude."""
from __future__ import annotations

import fnmatch
import os

import anthropic

from .github_client import ChangedFile

DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_DIFF_CHARS = 60_000  # keep prompts a sensible size for the prototype

# Files that aren't worth reviewing
IGNORE_PATTERNS = [
    "*.lock", "package-lock.json", "poetry.lock", "*.min.js", "*.min.css",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.svg", "*.pdf", "dist/*", "build/*",
]

SYSTEM_PROMPT = """You are a senior software engineer doing a code review on a git push.
Review ONLY the changes shown in the diff. Be concrete and concise.

Report, in this order, using Markdown:
1. **Summary** - one or two sentences on what the change does.
2. **Issues** - bugs, security problems, error handling gaps, performance problems.
   For each: severity (🔴 high / 🟠 medium / 🟡 low), `file:line` where possible, the problem, and a suggested fix.
3. **Suggestions** - readability, naming, tests, design (keep it short).
4. **Verdict** - one of: ✅ Looks good, ⚠️ Needs minor changes, ❌ Needs significant changes.

If there are no real issues, say so plainly - don't invent problems."""


def _should_review(f: ChangedFile) -> bool:
    if f.status == "removed" or not f.patch:
        return False
    return not any(fnmatch.fnmatch(f.filename, p) for p in IGNORE_PATTERNS)


def build_diff_text(files: list[ChangedFile]) -> tuple[str, list[str]]:
    """Concatenate reviewable patches, truncating if needed. Returns (diff_text, skipped_files)."""
    parts, skipped, total = [], [], 0
    for f in files:
        if not _should_review(f):
            skipped.append(f.filename)
            continue
        chunk = f"### {f.filename} ({f.status}, +{f.additions}/-{f.deletions})\n```diff\n{f.patch}\n```\n"
        if total + len(chunk) > MAX_DIFF_CHARS:
            skipped.append(f"{f.filename} (diff too large for this review)")
            continue
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts), skipped


def review_changes(files: list[ChangedFile], commit_message: str = "") -> str | None:
    """Returns review Markdown, or None if there was nothing to review."""
    diff_text, skipped = build_diff_text(files)
    if not diff_text:
        return None

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model=os.getenv("REVIEW_MODEL", DEFAULT_MODEL),
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Commit message:\n{commit_message or '(none)'}\n\nDiff:\n{diff_text}",
        }],
    )
    review = "".join(block.text for block in response.content if block.type == "text")

    if skipped:
        review += "\n\n<details><summary>Files not reviewed</summary>\n\n" + \
                  "\n".join(f"- {s}" for s in skipped) + "\n</details>"
    return review
