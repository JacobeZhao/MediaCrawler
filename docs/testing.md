# Testing and Verification

Run the primary local/CI verification entry point after Python changes from an
active, provisioned Python environment:

```powershell
python -m tools.verify
```

The verifier runs dependency and configuration contracts, compilation, and full
test discovery as separate labeled phases. It runs every phase for diagnostics
and returns a failure if any phase fails. It does not install or resolve
dependencies, so provision the declared environment before treating a full run
as a release gate. The focused commands below remain useful for diagnosis.

## Dependency Manifest Contract

`pyproject.toml` `[project].dependencies` is the canonical direct dependency
declaration. `requirements.txt` is its checked pip-compatible export and must
contain the same dependency strings in the same order. Run the focused drift
check with:

```powershell
python -m unittest discover -s tests -p test_dependency_contract.py -v
```

## Required Smoke Checks

- `GET /healthz`
- `GET /readyz`
- `GET /api/status`
- `GET /api/accounts`
- `POST /api/accounts/health_check`
- Confirm `/readyz` and `/api/status` expose separate `local` and `justoneapi`
  readiness/queue data when both providers are registered.
- Open `/` and confirm the frontend loads.

Local sandboxed runs can fail to reach Xiaohongshu with browser/network errors.
That is acceptable only if FastAPI starts, the UI loads, and runtime accounts are
not incorrectly invalidated.

## Regression Cases

- Startup configuration must preserve `CLI > process environment > .env >
  defaults`, fail atomically without exposing values, and reject a missing
  explicitly selected environment file.
- Windows launchers must validate bind ports before entering a restart loop;
  direct Uvicorn commands must pass their listener host and port as Uvicorn CLI
  arguments.
- Starting a second service process against the same runtime directory must fail
  because `service/runtime_lock.py` locks byte 0 of `data/service.lock`.
- `force=True` on search/creator tasks must be persisted into task params and
  must reach `TaskManager`.
- Requests without `provider` must remain compatible and create `local` tasks.
- The same search/creator input must deduplicate within one provider but not across
  `local` and `justoneapi`.
- A ready JustOneAPI task must run without a local browser account, and a long API
  request must not block the local provider worker.
- Resume must retain provider/checkpoint; recrawl must retain provider and clear the
  checkpoint.
- Retryable provider failures must respect `retry_at`, request budgets, and bounded
  retry counts. Persisted request metadata and surfaced errors must never contain the
  JustOneAPI token or a rendered authenticated URL.
- Request budgets must persist across claims/restarts. An expired task with an
  `inflight` provider request must become an unknown-outcome failure rather than be
  replayed automatically.
- Search comment crawling must only fetch comments for notes successfully saved
  in the current page iteration.
- `/api/accounts/health_check` must not change a captcha account to active or
  invalid unless the live probe succeeds.
- QR login temp profiles must be removed on cancel/expiry while successful
  sessions keep the adopted profile.
- SQLite schema changes require remote backup and duplicate-data inspection
  before adding unique indexes or migrations.

Mocked provider responses are sufficient for deterministic CI behavior, error
mapping, redaction, pagination, and normalization tests. They do not verify the live
upstream payload contract: run a controlled real-token contract probe before
production enablement, because the upstream OpenAPI schema leaves endpoint `data`
payloads untyped. Do not commit the token or captured authenticated URLs.
