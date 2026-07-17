# XHS Crawler Service Architecture

This project is a single-platform Xiaohongshu data collection service. It is designed
for one local Windows host, one uvicorn process, and local SQLite. Its default `local`
task provider uses Playwright browser profiles; the optional `justoneapi` provider
uses an outbound HTTP API instead.

Do not use `_backup_before_cleanup_20260625_102946/` for development.

## Runtime Flow

```text
start_xhs_service.py
  -> uvicorn service.app:app
      -> service.main.create_app()
          -> lifespan
              -> runtime single-instance lock
              -> service DB init
              -> optional local XHSCrawlerEngine / AccountPool start
              -> task executor registry
              -> TaskManager start
          -> routes/*
              -> services/*
                  -> service_db.py
                  -> TaskManager
                      -> local queue / worker -> AccountPool -> XHSCrawlerEngine
                      -> justoneapi queue / worker -> JustOneAPI HTTP client
```

## Module Responsibilities

- `service/main.py`: FastAPI composition root, middleware, route registration, static mounts, lifespan.
- `service/dependencies.py`: process-level singleton instances and dependency accessors.
- `service/routes/`: HTTP boundary only. Keep request/response concerns here.
- `service/schemas/`: Pydantic request schemas and input constraints.
- `service/services/`: application workflows. Avoid raw SQL here unless no repository exists yet.
- `service/service_db.py`: service database repository for tasks, accounts, note tags, leases, heartbeat.
- `service/task_manager.py`: provider-specific in-process queues and workers with DB
  lease, heartbeat, checkpoint, and deferred-retry management.
- `service/executors/`: common task executor contract, registry, and provider-specific
  execution logic.
- `service/account_pool.py`: account engine lifecycle, rotation, and soft health
  checks for the `local` provider only.
- `service/crawler_engine.py`: Playwright + XHS client orchestration. This is high-risk; refactor gradually.
- `media_platform/xhs/`: XHS protocol client, signing, login, parsing.
- `store/xhs/`, `database/`: crawler data persistence.
- `service/static/`: static frontend. `index.html` contains markup, `styles.css`
  contains layout, and `app.js` contains state, API calls, rendering, and events.

## Data Stores

- `data/service.db`: tasks, provider/checkpoint/retry metadata, provider request
  audit rows, accounts, note tags, and task leases.
- `database/sqlite_tables.db`: XHS notes, comments, creators.
- `browser_data/`: Playwright persistent browser profiles.

These runtime paths are not source code and must not be included in normal code review
or deployment diffs.

## Health Endpoints

- `/healthz`: process liveness only.
- `/readyz`: service readiness. It is `ok` when at least one enabled task provider is
  ready and includes readiness details for every registered provider.
- `/api/status`: UI-facing engine status plus per-provider readiness and queue sizes.

## Execution Providers

Task records persist `provider=local|justoneapi`; omitted values migrate/default to
`local`. Search and creator conflict detection includes the provider, and resume or
recrawl always uses the provider already stored on the task.

The two providers share task lifecycle and normalized content persistence, but not
execution infrastructure:

- `local` uses `AccountPool`, Playwright, the crawler rate limiter, and local circuit
  breaker.
- `justoneapi` uses its own HTTP client, request budget, retry policy, and response
  normalizer. It must never expose the query-string token in logs or task errors.

Each provider has a separate queue and worker, so a long JustOneAPI request does not
block local browser tasks. This is an alternative execution method for one-time
tasks only; there is no monitoring, scheduler, subscription, or periodic polling
component.

## Single-Process Rule

The service uses local SQLite, in-process queue state, and, when enabled, Playwright
persistent profiles. It must run as one uvicorn worker and one OS process per runtime
directory. `service/runtime_lock.py` enforces this at startup.

Do not enable multiple uvicorn workers unless queue state, browser profiles, account
state, and SQLite writes are externalized.
