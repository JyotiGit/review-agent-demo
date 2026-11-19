# AI Pull Request Review Agent

When a pull request is opened or updated, a GitHub Action runs, Claude reviews the changes,
and the feedback is posted as a review comment on the PR.

```
open / update PR ──▶ GitHub Actions ──▶ review_agent (Python) ──▶ Claude API
                                               │
                                               └──▶ review comment on the PR
```

## Files

```
.github/workflows/pr-review.yml   # runs the agent on pull requests
review_agent/
  pr_review.py      # entry point: reads the PR event, reviews, posts
  github_client.py  # GitHub API: PR details, changed files, post review
  reviewer.py       # prompt + Claude call + diff filtering
requirements.txt
```

## When it runs

| PR event | Reviewed? |
|---|---|
| PR opened | Yes |
| New commits pushed to the PR | Yes - a fresh review each time |
| PR reopened | Yes |
| Draft PR | No - reviewed once it's marked **Ready for review** |
| PR from a fork | No - GitHub doesn't give fork PRs access to secrets |

## Setup

1. Copy `.github/`, `review_agent/`, `requirements.txt` and `.gitignore` into your repo and push to `main`.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   `ANTHROPIC_API_KEY` = your key from platform.claude.com.
3. **Settings → Actions → General → Workflow permissions**: *Read and write permissions*.

`GITHUB_TOKEN` is created automatically for each run.

## Try it

```bash
git checkout -b test-review
# add or change some code
git add . && git commit -m "Test change" && git push -u origin test-review
```

On GitHub, click **Compare & pull request → Create pull request**. Within a minute or two the review
appears in the PR's **Conversation** tab. The **Checks** tab shows the run.

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
