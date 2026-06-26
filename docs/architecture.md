# XHS Crawler Service Architecture

This project is a single-platform Xiaohongshu crawler service. It is designed for one
local Windows host, one uvicorn process, local SQLite, and local Playwright browser
profiles.

Do not use `_backup_before_cleanup_20260625_102946/` for development.

## Runtime Flow

```text
start_xhs_service.py
  -> uvicorn service.app:app
      -> service.main.create_app()
          -> lifespan
              -> runtime single-instance lock
              -> service DB init
              -> default XHSCrawlerEngine start
              -> AccountPool start
              -> TaskManager start
          -> routes/*
              -> services/*
                  -> service_db.py
                  -> AccountPool / TaskManager / XHSCrawlerEngine
```

## Module Responsibilities

- `service/main.py`: FastAPI composition root, middleware, route registration, static mounts, lifespan.
- `service/dependencies.py`: process-level singleton instances and dependency accessors.
- `service/routes/`: HTTP boundary only. Keep request/response concerns here.
- `service/schemas/`: Pydantic request schemas and input constraints.
- `service/services/`: application workflows. Avoid raw SQL here unless no repository exists yet.
- `service/service_db.py`: service database repository for tasks, accounts, note tags, leases, heartbeat.
- `service/task_manager.py`: single in-process task worker with DB lease/heartbeat.
- `service/account_pool.py`: account engine lifecycle, rotation, soft health checks.
- `service/crawler_engine.py`: Playwright + XHS client orchestration. This is high-risk; refactor gradually.
- `media_platform/xhs/`: XHS protocol client, signing, login, parsing.
- `store/xhs/`, `database/`: crawler data persistence.
- `service/static/`: static frontend. `index.html` contains markup, `styles.css`
  contains layout, and `app.js` contains state, API calls, rendering, and events.

## Data Stores

- `data/service.db`: tasks, accounts, note tags, task leases.
- `database/sqlite_tables.db`: XHS notes, comments, creators.
- `browser_data/`: Playwright persistent browser profiles.

These runtime paths are not source code and must not be included in normal code review
or deployment diffs.

## Health Endpoints

- `/healthz`: process liveness only.
- `/readyz`: service readiness. It is `ok` only when the default engine or at least one pooled account is ready.
- `/api/status`: UI-facing engine and queue status.

## Single-Process Rule

The service uses local SQLite, in-process queue state, and Playwright persistent
profiles. It must run as one uvicorn worker and one OS process per runtime directory.
`service/runtime_lock.py` enforces this at startup.

Do not enable multiple uvicorn workers unless queue state, browser profiles, account
state, and SQLite writes are externalized.
