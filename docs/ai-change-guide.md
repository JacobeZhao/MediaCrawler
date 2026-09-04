# AI Change Guide

This guide is for future AI or human maintainers.

## Hard Rules

- Do not treat `browser_data/`, `data/`, `exports/`, `*.db`, or `*.log` as source code.
- Keep the service single-process unless the runtime model is redesigned.
- Run `python -m tools.verify` after Python changes; `docs/testing.md` owns the
  verification phases and result interpretation.
- Do not rewrite `service/crawler_engine.py` in one pass. It is the highest-risk module.

## Preferred Change Pattern

1. Put HTTP-only logic in `service/routes/`.
2. Put request schemas and validation in `service/schemas/`.
3. Put workflow logic in `service/services/`.
4. Put service DB access in `service/service_db.py` or a future repository module.
5. Keep platform protocol changes inside `media_platform/xhs/`.

## High-Risk Areas

- `media_platform/xhs/playwright_sign.py` and `xhs_sign.py`: signing behavior.
- `media_platform/xhs/client.py`: request semantics, captcha, pagination.
- `service/crawler_engine.py`: browser sessions, login, storage, task progress.
- `service/account_pool.py`: account rotation and status transitions.
- SQLite schema changes: require migration and remote backup first.

## Runtime Validation Checklist

- `GET /healthz`
- `GET /readyz`
- `GET /api/status`
- `GET /api/accounts`
- `POST /api/accounts/health_check`
- Open `/` in browser.
- Confirm no account is changed to `invalid` solely because `pong()` failed while login cookies exist.

## Deployment Checklist

- Stop remote service before replacing source.
- Back up remote project and runtime DB files.
- Do not overwrite remote `browser_data/` unless intentionally resetting logins.
- Deploy source excluding `.venv`, `browser_data`, `data`, logs, caches, and backup directories.
- Install dependencies in the remote venv.
- Start one process only.
- Verify `/readyz` and `/api/accounts`.
