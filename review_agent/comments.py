"""Formatting of the review on GitHub, and the accept / reject decision on each comment."""
from __future__ import annotations

import re

from .reviewer import Finding, Review

HEADER = "## 🤖 AI Code Review"
COMMENT_MARKER = "<!-- ai-review-comment -->"
DECISION_MARKER = "<!-- ai-decision -->"

SEVERITY = {"high": "🔴 **High**", "medium": "🟠 **Medium**", "low": "🟡 **Low**"}
VERDICT = {
    "looks_good": "✅ Looks good",
    "minor_changes": "⚠️ Needs minor changes",
    "significant_changes": "❌ Needs significant changes",
}
FOOTER = "<sub>React 👍 / 👎 to rate this comment · reply `/accept` or `/reject <reason>`</sub>"


def inline_comment_body(f: Finding) -> str:
    parts = [COMMENT_MARKER, f"{SEVERITY.get(f.severity, f.severity)} · `{f.category}`", "", f.comment]
    if f.suggestion:
        parts += ["", f"**Suggestion:** {f.suggestion}"]
    parts += ["", FOOTER]
    return "\n".join(parts)


def summary_body(review: Review, head_sha: str) -> str:
    counts = {s: sum(1 for f in review.findings + review.unplaced if f.severity == s) for s in SEVERITY}
    lines = [
        HEADER, "",
        f"**Summary:** {review.summary or '(none)'}",
        f"**Verdict:** {VERDICT.get(review.verdict, review.verdict)}",
        f"**Findings:** {len(review.findings) + len(review.unplaced)} "
        f"(🔴 {counts['high']} · 🟠 {counts['medium']} · 🟡 {counts['low']}), "
        f"{len(review.findings)} posted as inline comments",
    ]
    if not review.findings and not review.unplaced:
        lines += ["", "No problems found in the changed code. 🎉"]
    if review.unplaced:
        lines += ["", "**Other findings** (couldn't be attached to a changed line):"]
        lines += [f"- {SEVERITY.get(f.severity)} `{f.path}:{f.line}` · `{f.category}` — {f.comment}"
                  for f in review.unplaced]
    if review.dropped:
        lines += ["", f"_{review.dropped} lower-severity finding(s) not shown (limit is 10 comments)._"]
    if review.skipped_files:
        lines += ["", "<details><summary>Files not reviewed</summary>", ""]
        lines += [f"- {s}" for s in review.skipped_files] + ["</details>"]
    lines += ["", "---", f"<sub>Reviewed commit `{head_sha[:7]}`</sub>"]
    return "\n".join(lines)


def parse_decision(body: str) -> tuple[str, str] | None:
    """'/reject not relevant here' -> ('rejected', 'not relevant here'). None if it isn't a command."""
    first = (body or "").strip().split("\n", 1)[0].strip()
    m = re.match(r"^/(accept|reject)\b\s*(.*)$", first, re.IGNORECASE)
    if not m:
        return None
    return ("accepted" if m.group(1).lower() == "accept" else "rejected"), m.group(2).strip()[:200]


def parse_ai_comment(body: str) -> dict:
    """Read severity, category, text and decision back out of an AI comment (for reporting)."""
    sev = re.search(r"\*\*(High|Medium|Low)\*\*", body or "")
    cat = re.search(r"·\s*`(\w+)`", body or "")
    main = (body or "").split(f"\n\n{DECISION_MARKER}")[0]
    text_lines = []
    for line in main.splitlines()[2:]:  # skip the marker and the severity line
        if line.startswith("**Suggestion:**") or line.startswith("<sub>"):
            break
        if line.strip():
            text_lines.append(line.strip())
    decision = {"decision": "pending", "decided_by": "", "reason": ""}
    if DECISION_MARKER in (body or ""):
        m = re.search(r"(Accepted|Rejected)\*\* by @(\S+)(?: — (.*))?", body.split(DECISION_MARKER, 1)[1])
        if m:
            decision = {"decision": m.group(1).lower(), "decided_by": m.group(2), "reason": (m.group(3) or "").strip()}
    return {
        "severity": sev.group(1).lower() if sev else "",
        "category": cat.group(1) if cat else "",
        "comment": " ".join(text_lines),
        **decision,
    }


def with_decision(body: str, decision: str, user: str, reason: str) -> str:
    """Add (or replace) the decision line at the bottom of an AI comment."""
    base = body.split(f"\n\n{DECISION_MARKER}")[0]
    label = "✅ **Accepted**" if decision == "accepted" else "❌ **Rejected**"
    line = f"{label} by @{user}" + (f" — {reason}" if reason else "")
    return f"{base}\n\n{DECISION_MARKER}\n{line}"
