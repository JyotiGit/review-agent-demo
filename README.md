# AI Code Review Agent (prototype)

Every `git push` triggers a GitHub Actions job that:

1. reads the push event (which commits changed),
2. fetches the diff from the GitHub API,
3. sends it to Claude for review,
4. posts the review as a **comment on the pushed commit** and on the Actions run summary.

```
git push ──▶ GitHub Actions ──▶ review_agent (Python) ──▶ Claude API
                                       │
                                       └──▶ commit comment on GitHub
```

## Project layout

```
.github/workflows/
  code-review.yml       # on every push: review + log it
  review-feedback.yml   # on a comment on a commit: log the user's reply
  review-sync.yml       # hourly: log reactions and deleted reviews
review_agent/
  main.py           # entry point: reads push event, reviews, logs
  github_client.py  # GitHub API: diffs, comments, reactions
  reviewer.py       # prompt + Claude call + diff filtering
  events.py         # review summary, reply commands, reaction meanings
  store.py          # event log on the review-logs branch
  feedback.py       # records replies
  sync.py           # records reactions / deletions
  report.py         # event log -> CSV + summary
requirements.txt
```

## Setup (5 minutes)

1. **Create a repo** on GitHub and push this folder to it (or copy `.github/` and `review_agent/` into an existing repo).
2. **Get an Anthropic API key** at https://console.anthropic.com.
3. In the repo: **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `ANTHROPIC_API_KEY`, value: your key.
4. **Settings → Actions → General → Workflow permissions** → choose **Read and write permissions** (so the job can comment).
5. Push any change. Open the **Actions** tab to watch the run; the review appears as a comment on the commit.

`GITHUB_TOKEN` is supplied automatically by Actions — no setup needed.

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...          # personal access token with repo access
python -m review_agent.main --repo owner/name --sha <commit_sha> --dry-run
```

`--dry-run` prints the review instead of posting it.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `REVIEW_MODEL` | `claude-sonnet-5-5` | Claude model to use |

Ignored files and the max diff size are set at the top of `review_agent/reviewer.py`.

## Recording reviews and user actions

Every review and every reaction to it is logged to a branch called **`review-logs`** in the same repo
(created automatically on the first review). Each event is a small JSON file under `events/YYYY/MM/DD/`.

| Event | Recorded when | Recorded by |
|---|---|---|
| `review_posted` | the agent posts a review (with issue counts + verdict) | `code-review.yml` (on push) |
| `user_reply` | someone comments on a reviewed commit | `review-feedback.yml` (instantly) |
| `reaction_added` / `reaction_removed` | someone reacts 👍 👎 etc. on a review | `review-sync.yml` (hourly) |
| `review_deleted` | a review comment is deleted | `review-sync.yml` (hourly) |

Developers tell the agent what they did by replying on the commit with a command:

| Reply contains | Logged action |
|---|---|
| `/accept` | `accepted` |
| `/reject` | `rejected` |
| `/fixed` | `fixed` |
| `/false-positive` | `false_positive` |
| `/wontfix` | `wont_fix` |
| anything else | `replied` |

GitHub doesn't start workflows when someone reacts to a comment, so reactions are picked up by the hourly
sync. In a demo, open **Actions → AI Review - sync reactions → Run workflow** to sync immediately.

> `commit_comment` and scheduled workflows only run from the **default branch**, so make sure all three
> workflow files are committed there.

### Report

```bash
git clone --branch review-logs --single-branch https://github.com/<owner>/<repo>.git review-logs
python -m review_agent.report review-logs --out review_report.csv
```

This prints a summary (reviews, 👍/👎, accepted/rejected counts) and writes a CSV with one row per review
that opens in Excel or Google Sheets.

## Ideas for the next iteration

- Review **pull requests** (`on: pull_request`) and post **inline comments** on specific lines.
- Let the agent **read full files / repo context** (tools / function calling) rather than only the diff.
- Run as a **GitHub App + webhook server** (FastAPI) so it works across many repos without copying the workflow.
- Add rules per repo (e.g. a `.review-rules.md` the prompt includes).
- Chunk very large pushes instead of skipping files.
