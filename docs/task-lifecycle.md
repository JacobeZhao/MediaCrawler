# Task Lifecycle

Task records are stored in `data/service.db` table `tasks`.

## Statuses

- `pending`: queued and waiting for worker claim.
- `running`: claimed by the current worker.
- `paused`: worker cannot proceed, usually no healthy account or shutdown.
- `completed`: task finished and counts were written.
- `failed`: task failed permanently.

## Lease Model

`TaskManager` claims a task before running it:

- `lease_owner`: process-specific worker id.
- `heartbeat_at`: last progress heartbeat.
- `lease_expires_at`: claim expiry.

On startup, unfinished tasks are requeued because the service is designed as a single
local process. Do not run multiple service instances against the same DB.

## Retry and Account Switching

Recoverable account errors and captcha errors switch to another account. If all
available accounts fail, the task becomes `failed`.

## Resume and Recrawl

- Resume keeps existing data and requeues the same task id.
- Recrawl sets `force=True` and requeues the same task id.
- New search/creator tasks with `force=True` must persist that flag in `params`;
  otherwise the API bypasses conflict checks but execution still behaves like a
  normal resume.

The crawler skips already saved note ids when not forced.

## Single Instance

`service/runtime_lock.py` locks byte 0 of `data/service.lock`. A second process
using the same runtime directory must fail before starting browser, account pool,
or task worker state.

## Account Health

Account health checks are soft probes. A failed `pong()` with login cookies is
not enough to invalidate an account. Captcha status is sticky until a live probe
succeeds or the user refreshes the account.
