# Project Map

This project is a focused Xiaohongshu crawler service with a FastAPI backend,
a static operations console, local SQLite runtime state, and optional MySQL
sync tools.

## Entry Points

- `start_xhs_service.py`: starts uvicorn with `service.app:app`.
- `service/app.py`: exposes the FastAPI app instance.
- `service/main.py`: assembles routes, static files, lifecycle startup, crawler
  engine, account pool, and task manager.
- `ops/`: Windows foreground/supervised start scripts and account import helper.

## Backend Layers

- `service/routes/`: HTTP route functions only.
- `service/schemas/`: Pydantic request models.
- `service/services/`: application services for accounts, tasks, exports, and
  note queries.
- `service/task_manager.py`: in-process queue worker, task lease, heartbeat,
  retry/pause handling.
- `service/account_pool.py`: runtime account engines and account health state.
- `service/crawler_engine.py`: current crawler facade. It owns browser startup,
  login checks, search/creator/note crawling, and persistence calls. This is the
  highest-risk module and should be refactored behind tests.
- `service/service_db.py`: service runtime database access for tasks, accounts,
  leases, and tags.

## Platform and Storage

- `media_platform/xhs/`: Xiaohongshu client, signing, login, and extraction.
- `store/xhs/`: maps crawler results into database records.
- `database/`: SQLAlchemy session and ORM models for crawler data.
- `config/`: runtime paths and crawler configuration.
- `tools/sync_comments_to_dwd.py`: MySQL ODS-to-DWD sync for comment threads.
- `tools/create_search_tasks.py`: reusable task creation helper.

## Frontend

- `service/static/index.html`: DOM structure.
- `service/static/styles.css`: console layout and visual styles.
- `service/static/app.js`: state, API calls, rendering, and event handlers.

The frontend calls relative `/api/*` paths by default. To point it at another
backend, define this before loading `app.js`:

```html
<script>
window.__XHS_CONFIG__ = { apiBase: "http://<host>:<port>" };
</script>
```

## Runtime Data

Runtime state is not source code:

- `data/`: service DB and lock files.
- `browser_data/`: browser profiles and account login state.
- `database/*.db`: crawler SQLite data.
- `logs/`: service logs.
- `data_archive/`: local migration evidence and one-off snapshots. It is not
  source code and should not be read by default.

## Refactor Boundaries

Low-risk changes:

- routes, schemas, docs, frontend static files, and ops scripts.
- moving temporary scripts out of the project root.

Medium-risk changes:

- task service behavior, account service behavior, export and note query logic.

High-risk changes:

- `service/crawler_engine.py`, `media_platform/xhs/client.py`, `store/xhs/`,
  and database model constraints. Add focused tests before changing behavior.
