# Testing and Verification

Run this after Python changes:

```powershell
.\.venv\Scripts\python.exe -m compileall service config media_platform store database tools base cache model start_xhs_service.py
```

## Required Smoke Checks

- `GET /healthz`
- `GET /readyz`
- `GET /api/status`
- `GET /api/accounts`
- `POST /api/accounts/health_check`
- Open `/` and confirm the frontend loads.

Local sandboxed runs can fail to reach Xiaohongshu with browser/network errors.
That is acceptable only if FastAPI starts, the UI loads, and runtime accounts are
not incorrectly invalidated.

## Regression Cases

- Starting a second service process against the same runtime directory must fail
  because `service/runtime_lock.py` locks byte 0 of `data/service.lock`.
- `force=True` on search/creator tasks must be persisted into task params and
  must reach `TaskManager`.
- Search comment crawling must only fetch comments for notes successfully saved
  in the current page iteration.
- `/api/accounts/health_check` must not change a captcha account to active or
  invalid unless the live probe succeeds.
- QR login temp profiles must be removed on cancel/expiry while successful
  sessions keep the adopted profile.
- SQLite schema changes require remote backup and duplicate-data inspection
  before adding unique indexes or migrations.
