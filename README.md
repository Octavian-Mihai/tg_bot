# internbot

A Telegram bot that watches for new **IT / software / cybersecurity / DevOps internships in the
Montreal area** and sends them to me in a single batched message. It runs on a schedule in GitHub
Actions and never sends the same posting twice.

Official APIs only: the Adzuna API, public Greenhouse and Lever job-board APIs, and the Telegram
Bot API. No scraping, no unofficial clients.

## How it works

```mermaid
flowchart LR
    subgraph Sources
        A[Adzuna API]
        G[Greenhouse boards]
        L[Lever boards]
    end
    C[(companies.toml)] --> G
    C --> L
    A --> M
    G --> M
    L --> M
    M[main.py<br/>collect] --> F[filters.py<br/>internship + tech title]
    F --> D[storage.py<br/>SQLite dedupe]
    D --> N[formatting.py<br/>batch + split]
    N --> T[notifier.py<br/>Telegram]
    D <-. seen_jobs.db .-> S[(state branch)]
    CRON[GitHub Actions cron<br/>Toronto time slots] --> M
```

1. **Collect:** every source returns normalized `Job` objects (`id`, `title`, `company`,
   `location`, `url`, `source`). A failing source is logged and skipped; the run only fails if
   *every* source fails.
2. **Filter:** the title must look like an internship (`intern`, `stagiaire`, `stage`, `co-op`,
   `alternance`) *and* mention a tech term. It leans towards false positives over missed postings.
3. **Dedupe:** SQLite remembers what was already sent, by job ID and by (company, title) across
   different sources, so a posting listed on both Adzuna and a company board is sent once.
4. **Notify:** new jobs are batched into one message, split on job boundaries at Telegram's
   4,096-character limit. Jobs are marked as seen only after every message was delivered.

## Project layout

```
internbot/
  sources/        adzuna.py, greenhouse.py, lever.py, base.py (HTTP retries, location matching)
  config.py       loads companies.toml
  filters.py      internship + tech title filters
  formatting.py   message batching / splitting
  storage.py      SQLite seen-jobs store
  notifier.py     Notifier interface + TelegramNotifier
  main.py         orchestration
companies.toml    company boards to watch + location keywords
tests/            pytest suite
.github/workflows/daily.yml
```

## Setup

### 1. Accounts and keys
- **Telegram:** message `@BotFather`, run `/newbot`, keep the token. Send your bot any message,
  then run `python -m internbot.notifier --get-chat-id` to find your chat ID.
- **Adzuna:** register at <https://developer.adzuna.com> for a free app ID and key.

### 2. Run locally
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env        # fill in the four values; .env is gitignored
.venv/bin/python -m internbot.notifier        # sends "hello" to check Telegram
.venv/bin/python -m internbot.main --dry-run  # prints what it would send
.venv/bin/python -m internbot.main            # sends and records what it sent
.venv/bin/python -m pytest
```

| Variable | Purpose |
|---|---|
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | where to send |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna API |
| `INTERNBOT_DB` (optional) | SQLite path, default `seen_jobs.db` |
| `INTERNBOT_CONFIG` (optional) | alternative to `companies.toml` |

### 3. Deploy on GitHub Actions
1. Push this repo to GitHub.
2. Add the four secrets above under *Settings → Secrets and variables → Actions*.
3. Run the **internbot** workflow once manually (*Actions → Run workflow*) to verify.

**Schedule (Toronto time):** weekdays at 06, 08, 10, 12, 14, 16, 18, 20 and 22; weekends at 08,
12, 16 and 20. GitHub cron is UTC-only and Toronto switches between UTC-4 and UTC-5, so the cron
fires on every UTC hour that could matter and a guard step checks the real Toronto time. Runs
start a few minutes after the hour and GitHub may delay or occasionally skip scheduled runs.

**Persistence:** runners have no disk between runs, so the workflow restores `seen_jobs.db` from
an orphan `state` branch and force-pushes it back (as a single commit) when it changed. It is
durable, free and needs no extra accounts. The DB holds only job IDs, titles and URLs; the repo is
public, so never put secrets in it. Alternatives considered: `actions/cache` (evicted after 7
idle days, which would resend old postings), workflow artifacts (clunky to fetch across runs) and
an external database (extra account and dependency).

GitHub pauses scheduled workflows on a public repo after 60 days without repo activity; re-enable
it from the Actions tab if you get the email.

## Adding companies

Edit `companies.toml`:

```toml
[[company]]
name = "Example Inc"
ats = "greenhouse"        # or "lever"
slug = "example"          # boards.greenhouse.io/<slug> or jobs.lever.co/<slug>
```

Companies on other systems (Workday, SmartRecruiters, ...) are not supported. Many large Montreal
employers use those, so Adzuna also covers part of the gap.

## Limitations
- Title-only filtering: a vague title like "Summer Intern" is dropped.
- Same company and title from *different* sources is treated as one posting.
- Adzuna's Canadian coverage is uneven.
