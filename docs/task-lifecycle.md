# Task Lifecycle

Task records are stored in `data/service.db` table `tasks`.

## Statuses

- `pending`: queued and waiting for its provider worker to claim it.
- `running`: claimed by the matching provider worker.
- `paused`: execution cannot currently proceed, for example provider readiness,
  retry backoff, local account availability, or shutdown.
- `completed`: task finished and counts were written.
- `failed`: task failed permanently.

## Lease Model

`TaskManager` owns a separate in-process queue and worker for every registered
provider. It claims a task before running it:

- `lease_owner`: process-specific worker id.
- `heartbeat_at`: last progress heartbeat.
- `lease_expires_at`: claim expiry.

The stored provider determines the queue and executor; a task cannot be claimed by a
different provider worker. On startup, unfinished tasks are requeued only when their
provider is ready. Otherwise they remain paused, including tasks for a provider that
is disabled or unavailable in the current process. Do not run multiple service
instances against the same DB.

## Retry and Account Switching

For `local`, recoverable account and captcha errors may switch to another account;
when no healthy account can proceed, the task pauses for account-pool recovery.

For `justoneapi`, the HTTP client performs bounded retries for retryable transport or
upstream failures. If execution must wait longer, the task is paused with `retry_at`;
the provider requeue loop does not make it claimable before that time. Permanent
or otherwise non-retryable failures become `failed`. Every claim increments
`attempt_count`, while upstream request attempts are recorded separately without
credentials.

`manual_resume_required=1` is stronger than an ordinary pause. It is used when a
JustOneAPI request budget is exhausted, and the periodic requeue loop excludes it.
Submitting the same scoped search/creator task with a higher request budget preserves
the checkpoint and resumes it.

Each outbound provider attempt first persists its request count and an `inflight`
audit row. A response changes that row to `completed` or `unknown`. If a process dies
with an expired task lease and an `inflight` row, startup recovery marks the task
failed with an unknown outcome instead of replaying a request that may have been
billed.

## Checkpoints

Executors may persist `checkpoint_json` while a task owns its lease. A checkpoint is
written together with a heartbeat so a restarted or resumed task can continue from
the last committed provider position instead of replaying all completed pages,
details, comments, or replies.
Content writes remain idempotent because a request can finish remotely before its
checkpoint is committed.

## Resume and Recrawl

- Resume keeps existing data, provider, and checkpoint, then requeues the same task
  id.
- Recrawl keeps the provider, sets `force=True`, clears the checkpoint, and requeues
  the same task id.
- New search/creator tasks with `force=True` must persist that flag in `params`;
  otherwise the API bypasses conflict checks but execution still behaves like a
  normal resume.

The crawler skips already saved note ids when not forced.

Provider selection is part of task identity. The same search/creator input can be
submitted once to each provider without being treated as the same active task.

## Single Instance

`service/runtime_lock.py` locks byte 0 of `data/service.lock`. A second process
using the same runtime directory must fail before starting browser, account pool,
or task worker state.

## Account Health

Account health checks are soft probes. A failed `pong()` with login cookies is
not enough to invalidate an account. Captcha status is sticky until a live probe
succeeds or the user refreshes the account.
