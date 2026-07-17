# Technical Debt

This file tracks known debt that should not be solved by broad, untested
rewrites.

## High-Risk Core

- `service/crawler_engine.py` is a facade with too many responsibilities:
  browser lifecycle, login, cookie handling, XHS API orchestration, task
  execution, persistence calls, progress callbacks, and error classification.
- `service/service_db.py` mixes schema creation, migrations, task repository,
  account repository, tag repository, and live crawler-data aggregation.
- `service/task_manager.py` still combines provider queues, leases, deferred
  retries, recovery, and worker lifecycle in one module. Provider-specific
  execution is now delegated through the executor registry.
- `service/executors/justoneapi.py` combines search, creator, note, comment,
  reply, request-budget, and checkpoint orchestration. Split it only behind
  the existing characterization tests.
- `store/xhs/` uses implicit context for `source_keyword` and a partial update
  strategy that should be made explicit.

## Operations And Context Debt

- Package metadata reports version `0.1.0` while runtime settings, OpenAPI, and
  `/version` report `1.0.0`. Choose one release version before consolidating it.
- `exports/` contains untracked generated output but is not ignored. Confirm its
  ownership policy before making it a repository-wide ignore rule.
- Application shutdown does not explicitly dispose the cached SQLAlchemy async
  engines in `database/db_session.py`. Process exit releases them, but in-process
  lifecycle tests and reload tooling can retain SQLite file handles.
- The Windows supervisor validates its restart delay as an integer but not as a
  nonnegative value; a negative delay fails only after a child process exits.

## Recommended Refactor Order

1. Add tests around task resume/recrawl, account captcha transitions, note
   upsert, and task lease recovery.
2. Extract service DB repositories without changing behavior.
3. Add a centralized error model for account/auth/captcha/rate-limit failures.
4. Extract browser session management from `XHSCrawlerEngine` while keeping the
   engine as a compatibility facade.
5. Replace implicit global crawler options with explicit options objects.
6. Split store mapping from persistence and clarify full upsert vs metrics-only
   update.

## Recently Reduced

- The supported Python launch paths now load a strict root `.env` before
  settings are frozen. CLI and inherited process values retain precedence,
  malformed files fail atomically without exposing values, and launcher-order
  contract tests cover direct app import, the Windows supervisor, and the
  foreground wrapper.
- `TaskManager` now requires the canonical `ExecutorRegistry`; the unused
  `TaskManager(pool)` adapter and single-queue private aliases were removed
  after repository-wide reference checks.
- `TaskService` no longer stores an unused `XHSCrawlerEngine`, so its task API
  workflow is no longer coupled to the local Playwright provider.
- JustOneAPI creator checkpoint/resume and share-link note/tag attribution now
  have deterministic executor contract tests in addition to the existing
  search, budget, comment-resume, and error-policy coverage.
- JustOneAPI task defaults and validation bounds now live in
  `service/providers/justoneapi/options.py`; schema validation, task scope,
  legacy executor parsing, and transport defaults share that provider-owned
  source while retaining their distinct layer behavior.

## Do Not Do

- Do not rewrite the crawler core and storage layer in the same change.
- Do not delete `browser_data/` or active service DB files as part of source
  cleanup.
- Do not rely on files under `_backup_before_cleanup_*/` for active development.
