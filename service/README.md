# Service Package

`service/` contains the FastAPI application and the runtime orchestration around
the Xiaohongshu crawler.

## Boundaries

- `main.py`: application composition, route registration, static mounts, and
  lifecycle startup/shutdown.
- `app.py`: uvicorn-compatible app export only.
- `routes/`: HTTP boundary. Keep request parsing and HTTP status mapping here.
- `schemas/`: Pydantic request models and input constraints.
- `services/`: application workflows for accounts, tasks, notes, exports, and QR
  login sessions.
- `service_db.py`: service runtime database access for tasks, accounts, tags,
  leases, and heartbeats.
- `task_manager.py`: provider-aware in-process queues, workers, checkpoints, and
  lease management.
- `executors/`: the executor contract and the separate `local` and `justoneapi`
  one-time task execution paths.
- `account_pool.py`: pooled account crawler engines and account health state used
  only by the `local` provider.
- `crawler_engine.py`: current crawler facade over Playwright, the XHS client,
  crawl execution, and persistence calls.
- `static/`: no-build frontend served by FastAPI.

## Change Rules

- Do not split `crawler_engine.py` without adding focused tests first.
- Do not run multiple uvicorn workers against one runtime directory.
- Keep provider-specific network, retry, and normalization behavior behind the
  executor boundary; do not route `justoneapi` through Playwright or `AccountPool`.
- Keep routes thin; put orchestration in `services/`.
- Keep runtime data under ignored directories such as `data/`, `browser_data/`,
  and `logs/`.
