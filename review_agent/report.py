"""Turns the event log into a CSV (one row per review) and prints a summary.

    git clone --branch review-logs --single-branch <your repo url> review-logs
    python -m review_agent.report review-logs --out review_report.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

COLUMNS = [
    "review_comment_id", "posted_at", "commit_sha", "branch", "pusher", "verdict",
    "issues_high", "issues_medium", "issues_low", "thumbs_up", "thumbs_down",
    "replies", "last_action", "last_action_by", "deleted", "review_url",
]


def load_events(root: Path) -> list[dict]:
    events = []
    for f in sorted((root / "events").rglob("*.json")):
        try:
            events.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            print(f"Skipping unreadable {f}", file=sys.stderr)
    return sorted(events, key=lambda e: e["timestamp"])


def build_rows(events: list[dict]) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for e in events:
        rid = e.get("review_comment_id")
        if rid is None:
            continue
        row = rows.setdefault(rid, {c: "" for c in COLUMNS} | {
            "review_comment_id": rid, "thumbs_up": 0, "thumbs_down": 0, "replies": 0, "deleted": False,
        })
        t = e["type"]
        if t == "review_posted":
            row.update(posted_at=e["timestamp"], commit_sha=e.get("commit_sha"), branch=e.get("branch"),
                       pusher=e.get("pusher"), verdict=e.get("verdict"), issues_high=e.get("issues_high"),
                       issues_medium=e.get("issues_medium"), issues_low=e.get("issues_low"),
                       review_url=e.get("review_url"))
        elif t == "user_reply":
            row["replies"] += 1
            if e.get("action") != "replied":
                row.update(last_action=e["action"], last_action_by=e.get("user"))
        elif t in ("reaction_added", "reaction_removed"):
            delta = 1 if t == "reaction_added" else -1
            if e.get("reaction") == "+1":
                row["thumbs_up"] += delta
            elif e.get("reaction") == "-1":
                row["thumbs_down"] += delta
        elif t == "review_deleted":
            row["deleted"] = True
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description="Report on AI review feedback")
    p.add_argument("logs_dir", type=Path, help="local checkout of the review-logs branch")
    p.add_argument("--out", type=Path, default=Path("review_report.csv"))
    args = p.parse_args()

    events = load_events(args.logs_dir)
    rows = build_rows(events)
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sorted(rows.values(), key=lambda r: str(r["posted_at"])))

    total = len(rows)
    with_feedback = sum(1 for r in rows.values() if r["replies"] or r["thumbs_up"] or r["thumbs_down"])
    actions = Counter(r["last_action"] for r in rows.values() if r["last_action"])
    print(f"Events: {len(events)}   Reviews: {total}   With any feedback: {with_feedback}")
    print(f"👍 {sum(r['thumbs_up'] for r in rows.values())}   👎 {sum(r['thumbs_down'] for r in rows.values())}")
    for action, n in actions.most_common():
        print(f"  {action}: {n}")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
