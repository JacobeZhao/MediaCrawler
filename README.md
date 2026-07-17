# XHS Crawler Service

This repository contains the custom Xiaohongshu crawler web service restored from the Tianyi Cloud host.

## Active Runtime Code

- `start_xhs_service.py`: service entry point.
- `service/`: FastAPI API, application services, task/account management, crawler orchestration, and the custom static frontend.
- `ops/`: Windows start, supervisor, and account import helpers.
- `media_platform/xhs/`: Xiaohongshu client, login, signing, parsing, and field definitions.
- `store/xhs/`, `database/`, `config/`, `tools/`, `base/`, `cache/`, `model/`: runtime dependencies used by the XHS service path.
- `libs/stealth.min.js`: browser stealth script used by `service/crawler_engine.py`.

Removed source and runtime files are archived under `_backup_before_cleanup_*`.
That backup directory is not part of the active codebase and should not be read or used during normal development.

## Start

```powershell
python start_xhs_service.py --host 0.0.0.0 --port 8088 --headless
```

Open:

```text
http://127.0.0.1:8088/
```

Configuration priority is: CLI arguments > existing process environment >
the root `.env` file > defaults. All supported Python launch paths load `.env`
before application settings are created. Set `XHS_ENV_FILE` in the parent
process to use another file; `XHS_ENV_FILE` entries inside an environment file
are rejected to prevent chained loads.

Useful health endpoints:

- `GET /healthz`: process liveness.
- `GET /readyz`: readiness by task provider.
- `GET /version`: service version metadata.
- `GET /api/status`: crawler engine plus provider readiness and queue status.

The current deployment model is one uvicorn process with one in-process queue and
worker per registered task provider. Do not run multiple uvicorn workers unless the
task queues, QR sessions, account pool, browser state, and SQLite coordination are
externalized.

One-time `search`, `creator`, and `note` tasks accept `provider=local|justoneapi`.
The default is `local`, so existing clients continue to use Playwright and the local
account pool. `justoneapi` is an alternative outbound API execution path; it does not
add monitoring, subscriptions, scheduling, or periodic jobs. See `docs/api.md` and
`docs/config.md` before enabling it.

## Architecture

The FastAPI app is assembled in `service/main.py`; `service/app.py` is only the uvicorn-compatible entry module.

- `service/routes/`: HTTP route handlers.
- `service/schemas/`: request DTOs.
- `service/services/`: application services for tasks, accounts, note queries, QR sessions, and export.
- `service/service_db.py`: service database repository for tasks, accounts, tags, task lease, and heartbeat state.
- `service/executors/`: provider-specific task executors and executor registry.
- `service/crawler_engine.py`: XHS browser/client orchestration. This is still the highest-risk core and should be refactored gradually.

The static frontend lives in `service/static/`: `index.html` for markup, `styles.css` for layout, and `app.js` for state, API calls, and rendering. API calls go through a single frontend helper and can be pointed at a separate backend by setting `window.__XHS_CONFIG__.apiBase` before the app initializes.

More detail for future maintainers:

- `docs/architecture.md`
- `docs/project-map.md`
- `docs/api.md`
- `docs/frontend.md`
- `docs/technical-debt.md`
- `ops/README.md`
- `docs/task-lifecycle.md`
- `docs/config.md`
- `docs/testing.md`
- `docs/ai-change-guide.md`

## Runtime Data

These paths are runtime state and are ignored by Git:

- `data/`
- `browser_data/`
- `archive/`
- `data_archive/`
- `logs/`
- `database/*.db`
- `service/*.db`
- `*.log`
