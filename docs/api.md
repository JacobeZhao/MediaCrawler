# API Contract

The frontend in `service/static/index.html` calls the FastAPI service through
relative `/api/*` paths unless `window.__XHS_CONFIG__.apiBase` is set.

## Health

- `GET /healthz`: process liveness only.
- `GET /readyz`: returns `ok` only when the default engine or at least one pooled
  account is ready.
- `GET /api/status`: default engine status and queue size.
- `GET /version`: service name and version.

## Accounts

- `GET /api/accounts`: list account DB state and runtime state.
- `POST /api/accounts`: add a cookie-based account.
- `POST /api/accounts/{id}/cookie`: replace an account cookie and verify it.
- `DELETE /api/accounts/{id}`: remove account and stop its runtime engine.
- `POST /api/accounts/health_check`: soft account probe.
- `POST /api/accounts/qrcode/start`: start the current frontend QR-login flow.
- `GET /api/accounts/qrcode/{session_id}/poll`: poll QR-login status.
- `DELETE /api/accounts/qrcode/{session_id}`: cancel and clean up a QR-login session.

Health checks must not mark an account invalid solely because `pong()` fails
while the browser still has login cookies. A captcha account must remain captcha
unless a real probe succeeds.

## Legacy Login Routes

`service/routes/login.py` keeps older `/api/login/*` endpoints for compatibility
with earlier tooling. The current frontend uses `/api/accounts/qrcode/*` and
`/api/accounts` instead.

## Tasks

- `POST /api/tasks/search`: create one keyword search task.
- `POST /api/tasks/batch_search`: create keyword search tasks.
- `POST /api/tasks/creator`: create one creator task.
- `POST /api/tasks/batch_creator`: create creator tasks.
- `POST /api/tasks/note`: crawl explicit note URLs or IDs.
- `GET /api/tasks`: list tasks.
- `GET /api/tasks/{id}`: get task details.
- `POST /api/tasks/{id}/resume`: resume without forced recrawl.
- `POST /api/tasks/{id}/recrawl`: resume with `force=True`.

`force=True` is both an API conflict bypass and an execution flag. It must be
stored in the task params so `TaskManager` can pass it to the crawler.

## Notes and Export

- `GET /api/notes`: query saved notes with bounded `limit`.
- `GET /api/notes/{note_id}/images`: list local images for a validated note id.
- `GET /api/export/notes`: export saved note/comment data.

Do not let user input select arbitrary DB fields or filesystem paths.
