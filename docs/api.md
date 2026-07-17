# API Contract

The frontend in `service/static/index.html` calls the FastAPI service through
relative `/api/*` paths unless `window.__XHS_CONFIG__.apiBase` is set.

## Health

- `GET /healthz`: process liveness only.
- `GET /readyz`: returns `ok` when at least one enabled task provider is ready and
  includes the readiness of each registered provider.
- `GET /api/status`: default engine status, total queue size, and per-provider
  readiness and queue sizes.
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

All task-creation requests accept these common fields:

- `provider`: `local` or `justoneapi`; omitted values default to `local` for backward
  compatibility.
- `provider_options`: optional JustOneAPI execution controls. It is applied only when
  `provider` is `justoneapi`.

For example:

```json
{
  "keyword": "camping",
  "max_notes": 20,
  "provider": "justoneapi",
  "provider_options": {
    "include_details": true,
    "include_comments": false,
    "include_replies": false,
    "max_pages": 3,
    "max_requests": 20,
    "note_type": "ALL",
    "time_filter": "ALL"
  }
}
```

`provider_options` fields and defaults:

- `include_details=true`: request note detail enrichment when supported.
- `include_comments=false`: fetch comments after notes.
- `include_replies=false`: fetch comment replies; requires `include_comments=true`.
- `max_pages=3`: provider pagination limit, from 1 to 100.
- `max_requests=20`: task request budget, from 1 to 1000 and still bounded by the
  server-side `JUSTONEAPI_MAX_REQUESTS_PER_TASK` limit. The count persists across
  retries and service restarts.
- `note_type=ALL`: `ALL`, `NORMAL_NOTE`, or `VIDEO_NOTE`.
- `time_filter=ALL`: `ALL`, `ONE_DAY`, `ONE_WEEK`, or `HALF_YEAR`.

`days_limit` remains a local-crawler field. JustOneAPI requests must use
`provider_options.time_filter`; sending a non-zero `days_limit` with that provider is
rejected instead of silently changing the requested time range.

Search/creator duplicate detection is provider-specific, so the same input may have
one active local task and one active JustOneAPI task. Task responses and task detail
records expose the selected provider. Resume and recrawl retain that provider; they
never silently fall back to local crawling.

When the request budget is exhausted before the requested scope is complete, the task
is paused with `manual_resume_required=1`; it is not retried automatically. Submit the
same search or creator task with a higher `max_requests` value to continue from its
checkpoint. A transport outcome marked unknown is failed and likewise requires an
explicit user decision before retry, because the upstream request may already have
been billed.

Explicit note tasks support resume but not the recrawl endpoint. Search and creator
recrawl clear their provider checkpoint and set `force=True`.

`force=True` is both an API conflict bypass and an execution flag. It must be
stored in the task params so `TaskManager` can pass it to the crawler.

JustOneAPI credentials are server configuration and must never be sent in a task
request. The upstream service authenticates with a query parameter; URLs and errors
returned by this service must redact that token. The upstream OpenAPI schema leaves
some `data` payloads untyped, so a real-token endpoint contract probe is required
before treating production field coverage as verified.

These endpoints create finite, one-time tasks. They do not create monitors,
schedules, subscriptions, or recurring collection jobs.

## Notes and Export

- `GET /api/notes`: query saved notes with bounded `limit`.
- `GET /api/notes/{note_id}/images`: list local images for a validated note id.
- `GET /api/export/notes`: export saved note/comment data.

Do not let user input select arbitrary DB fields or filesystem paths.
