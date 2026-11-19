# AI Pull Request Review Agent

When a pull request is opened or updated, a GitHub Action runs and Claude reviews the changes.
Each finding is posted as an **inline comment on the changed line**, plus a short summary.
Developers rate each comment with 👍 / 👎 and **accept or reject** it by replying.

```
open / update PR ──▶ pr-review.yml ──▶ Claude ──▶ summary + inline comments on the PR
reply /accept or /reject on a comment ──▶ pr-feedback.yml ──▶ comment marked Accepted / Rejected
```

## Files

```
.github/workflows/
  pr-review.yml     # runs the review on pull requests
  pr-feedback.yml   # handles /accept and /reject replies
review_agent/
  pr_review.py      # entry point: reads the PR, reviews, posts inline comments
  pr_feedback.py    # marks a comment as accepted / rejected
  reviewer.py       # prompt + Claude call (structured output) + diff handling
  comments.py       # how comments and decisions look on GitHub
  github_client.py  # GitHub API calls
requirements.txt
```

## What a review looks like

**Summary** (in the Conversation tab): what the PR does, a verdict, and finding counts.

**Inline comment** (on the changed line, also in the Files changed tab):

> 🔴 **High** · `security`
>
> Hardcoded password.
>
> **Suggestion:** Read it from an environment variable.
>
> <sub>React 👍 / 👎 to rate this comment · reply `/accept` or `/reject <reason>`</sub>

- Every finding is tagged with a **severity** (high / medium / low) and a **category**
  (correctness / security / maintainability).
- At most **10** comments per review; the most severe are kept.
- A finding that can't be pinned to a changed line is listed in the summary instead.

## Rating and deciding

| You want to… | Do this |
|---|---|
| Rate a comment | Click 😀 on the comment → 👍 or 👎 |
| Accept it | Reply in that comment's thread: `/accept` (optionally add a note) |
| Reject it | Reply: `/reject <reason>`, e.g. `/reject b is never 0 here` |
| Change your mind | Reply again - the latest decision wins |

Within a few seconds the bot reacts 👍 to your reply and adds a line to the AI comment:
`✅ Accepted by @JyotiGit` or `❌ Rejected by @JyotiGit — <reason>`.

## When the review runs

| PR event | Reviewed? |
|---|---|
| PR opened / reopened | Yes |
| New commits pushed to the PR | Yes - a fresh review each time |
| Draft PR | No - reviewed once it's marked **Ready for review** |
| PR from a fork | No - GitHub doesn't give fork PRs access to secrets |

## Setup

1. Copy `.github/`, `review_agent/`, `requirements.txt` and `.gitignore` into your repo and push to `main`.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   `ANTHROPIC_API_KEY` = your key from platform.claude.com.
3. **Settings → Actions → General → Workflow permissions**: *Read and write permissions*.
4. Open a **new** PR from a branch created after step 1, so the branch contains both workflow files.

`GITHUB_TOKEN` is created automatically for each run.

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
python -m review_agent.pr_review --repo JyotiGit/review-agent-demo --pr 1 --dry-run
```

## Settings

| Env var | Default | Purpose |
|---|---|---|
| `REVIEW_MODEL` | `claude-sonnet-5-5` | Claude model to use (`claude-haiku-5-5` is cheaper for testing) |
