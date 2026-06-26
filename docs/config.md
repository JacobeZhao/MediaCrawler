# Configuration

Configuration priority:

```text
CLI arguments > environment variables > defaults in config/settings.py
```

Important variables:

- `HOST`, `PORT`: bind address.
- `HEADLESS`: Playwright headless mode.
- `CDP_CONNECT_EXISTING`: usually `false` for service mode.
- `XHS_INTERNATIONAL`: default `false`; `true` switches to `rednote.com`.
- `SQLITE_DB_PATH`: crawler content SQLite path.
- `SERVICE_DB_PATH`: service task/account SQLite path.
- `RUNTIME_LOCK_PATH`: single-instance lock path.
- `CRAWLER_MIN_SLEEP_SEC`, `CRAWLER_MAX_SLEEP_SEC`: crawl pacing.

Runtime paths:

- `.venv/`
- `data/`
- `data_archive/`
- `browser_data/`
- `archive/`
- `logs/`
- `database/*.db`
- `service/*.db`
- `*.log`

These are ignored by Git and should not be deployed as source.
