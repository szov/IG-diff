# IG-diff

Automates your own Instagram data export, diffs followers vs following, serves the result on a local dashboard.

Single-account design: one IG session per profile directory. Drives your account's official export flow in a real browser.

## Stack

FastAPI + uvicorn, Playwright + Camoufox (headed, or headless; `xvfb-run` on display-less servers), loguru, python-dotenv, filelock. Python 3.12, managed with uv.

## Quickstart

```bash
cp .env.example .env  # fill in IG_PASSWORD and IG_API_KEY
uv sync
uv run camoufox fetch
uv run python -m igdiff.auth --headed        # log in once, session is saved to profiles/
uv run python -m web.server --headed         # dashboard at http://127.0.0.1:8000/
```

Flags (`--profile NAME`, `--profile-dir PATH`, `--headless`, `--headed`) work on all entry points. Run from the repo root.

## Endpoints

| Method | Path | Auth | What |
|---|---|---|---|
| GET | `/` | none | Dashboard |
| GET | `/data` | key | Latest result JSON |
| POST | `/trigger` | key | Start an export run in the background |

Key goes in `?key=` or the `X-API-Key` header. The server refuses to start without `IG_API_KEY`.

## Layout

```text
igdiff/            automation package
  config.py        flags, env vars, shared paths
  browser.py       Camoufox launch (persistent profile, download dir)
  interactions.py  realistic clicks/typing, export password confirmation
  exporter.py      export request, download, extraction, analysis flow
  analyzer.py      followers/following diff
  auth.py          one-time manual login, saves the session
  log_config.py    logging setup
web/               dashboard app
  server.py        FastAPI app, key-gated trigger/data endpoints
  templates/
    index.html     dashboard
```

Runtime dirs (`profiles/`, `output/`, `downloaded_files/`, `logs/`, `dashboard_data.json`) live at the repo root and are gitignored.

## Notes

- Export generation takes minutes; the runner retries until the file is ready.
- Display-less server: `xvfb-run -a uv run python -m web.server --headed`.
- Automates your own account's official export flow; use responsibly.

## Future features

- Multi-account: per-profile credentials and schedules.
- Status-aware export waiting (poll for readiness instead of fixed retries).
- Notifications on new results (webhook or email).
- CSV export of the diff.
