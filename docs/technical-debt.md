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

- The administrative API has no authentication, permits all CORS origins, and
  the normal launcher binds to `0.0.0.0`. Candidate-account workflows also
  intentionally return passwords and cookies to the current operator console.
  Do not expose this service to an untrusted network. Choosing loopback-only
  defaults or adding authentication/CSRF protection is a product/deployment
  decision and must be completed before broader exposure.
- Package metadata reports version `0.1.0` while runtime settings, OpenAPI, and
  `/version` report `1.0.0`. Choose one release version before consolidating it.
- SQLite schema upgrades are cumulative startup code rather than versioned
  migrations. The content schema can merge/delete duplicate business keys
  before adding unique indexes; future destructive changes need an explicit
  migration ledger, preflight report, and recovery rehearsal.
- Dependencies are declared consistently in `pyproject.toml` and
  `requirements.txt`, but there is no lockfile or automated parity/CI gate.

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

- Application shutdown now disposes cached SQLAlchemy async engines and clears
  their schema-initialization state, with a focused lifecycle regression test.
- The Windows supervisor now rejects negative restart delays during configuration
  loading instead of crashing after a child process exits.
- SQLite WAL/SHM sidecars are ignored for both runtime database locations without
  deleting or modifying active database files.
- The documented MySQL comment-sync tool now declares its `pymysql` dependency in
  both package manifests.
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
- Local task lease loss now escapes crawler progress callbacks before further
  comment writes and leaves the browser account ready for the replacement owner.
- Runtime logs and persisted task errors redact credential-bearing URLs, headers,
  cookies, passwords, and provider response bodies; content-store logs are ID-only.
- Generated `exports/` output is ignored, and obsolete backup/restore markers were
  removed after their directories were explicitly deleted.
- Expired QR sessions are rejected on access, and application shutdown now closes
  every unadopted temporary QR engine/profile.

## Do Not Do

- Do not rewrite the crawler core and storage layer in the same change.
- Do not delete `browser_data/` or active service DB files as part of source
  cleanup.
