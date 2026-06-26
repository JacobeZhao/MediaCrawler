# Technical Debt

This file tracks known debt that should not be solved by broad, untested
rewrites.

## High-Risk Core

- `service/crawler_engine.py` is a facade with too many responsibilities:
  browser lifecycle, login, cookie handling, XHS API orchestration, task
  execution, persistence calls, progress callbacks, and error classification.
- `service/service_db.py` mixes schema creation, migrations, task repository,
  account repository, tag repository, and live crawler-data aggregation.
- `service/task_manager.py` knows task types and platform-specific error
  behavior directly.
- `store/xhs/` uses implicit context for `source_keyword` and a partial update
  strategy that should be made explicit.

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

## Do Not Do

- Do not rewrite the crawler core and storage layer in the same change.
- Do not delete `browser_data/` or active service DB files as part of source
  cleanup.
- Do not rely on files under `_backup_before_cleanup_*/` for active development.
