# Recursive Coverage Manifest

Baseline: `f7f99aeff476c3cbe2959cbc69130a02918c57ce`. Each tracked path below appears exactly once. The short record states its owner and function; detailed callers, state, side effects, configuration, confidence, and unknowns are merged in `current-state.md` and C1-C5.

## Root (10/10)

`.env.example` config template; `.gitignore` exclusion policy; `.python-version` interpreter selector; `LICENSE` legal boundary; `README.md` project entry guide; `RUNTIME_DO_NOT_READ.md` protected metadata-only instruction; `pyproject.toml` package/dependency metadata; `requirements.txt` pip dependency mirror; `start_xhs_service.py` CLI/Uvicorn launcher; `var.py` ambient crawl attribution context.

## Base And Cache (4/4)

`base/__init__.py` compatibility marker; `base/base_crawler.py` abstract crawler/login/store/client contracts; `cache/__init__.py` source package marker; `cache/local_cache.py` active expiring login cache.

## Configuration (6/6)

`config/README.md` ownership guide; `config/__init__.py` wildcard compatibility facade; `config/base_config.py` legacy crawler globals; `config/db_config.py` content-DB path facade; `config/settings.py` frozen environment settings; `config/xhs_config.py` XHS compatibility constants.

## Content Database (3/3)

`database/__init__.py` package marker; `database/db_session.py` async engines/sessions/startup schema repair; `database/models.py` creator/note/comment/attribution ORM schema.

## Documentation (11/11)

`docs/README.md` index; `docs/ai-change-guide.md` change governance; `docs/api.md` HTTP contract; `docs/architecture.md` runtime topology; `docs/config.md` configuration contract; `docs/frontend.md` console contract; `docs/mysql-ai-platform.md` external MySQL context; `docs/project-map.md` ownership map; `docs/task-lifecycle.md` task state model; `docs/technical-debt.md` prior debt ledger; `docs/testing.md` verification contract.

## Vendored Asset (1/1)

`libs/stealth.min.js` runtime-loaded minified browser evasions asset; provenance/regeneration unknown.

## XHS Platform (10/10)

`media_platform/__init__.py` namespace marker; `media_platform/xhs/__init__.py` field-export facade; `client.py` signed XHS transport; `exception.py` protocol errors; `extractor.py` response/HTML extraction; `field.py` enums; `help.py` URL/signing helpers; `login.py` browser login; `playwright_sign.py` xhshow adapter; `xhs_sign.py` signing primitives.

## Models (2/2)

`model/__init__.py` marker; `model/m_xiaohongshu.py` note/creator URL DTOs.

## Operations (4/4)

`ops/README.md` runbook; `ops/import_xhs_cookie_file.ps1` account-import API client; `ops/start-windows-foreground.cmd` foreground launcher; `ops/supervisor_windows.py` restart/log supervisor.

## Service Core (16/16)

`service/README.md` boundary guide; `service/__init__.py` marker; `account_pool.py` account-engine lifecycle; `app.py` ASGI export; `circuit_breaker.py` risk pause; `crawler_engine.py` local crawler facade; `dependencies.py` singleton composition; `image_downloader.py` remote image cache; `main.py` FastAPI/lifespan composition; `proxy_config.py` proxy validation/masking; `rate_limiter.py` pacing/budgets; `runtime_env.py` strict environment loader; `runtime_lock.py` user-owned process lock; `service_db.py` operational schema/repositories; `task_manager.py` queues/leases/recovery; `static/README.md` frontend boundary guide.

## Domain (3/3)

`service/domain/__init__.py` exports; `crawl_result.py` provider-neutral result; `xhs_content.py` canonical content records.

## Executors (5/5)

`service/executors/__init__.py` lazy public facade; `base.py` execution/readiness contracts; `justoneapi.py` remote workflow/budget/checkpoint executor; `local.py` account/crawler adapter; `registry.py` provider registry.

## Providers (7/7)

`service/providers/__init__.py` namespace; `service/providers/justoneapi/__init__.py` public facade; `client.py` HTTPS/token transport; `errors.py` failure policy; `models.py` envelopes/audits; `normalizer.py` upstream-to-domain mapping; `options.py` shared defaults/bounds.

## Routes (8/8)

`service/routes/__init__.py` router exports; `accounts.py` account/candidate/QR endpoints; `export.py` XLSX endpoint; `login.py` legacy login routes; `notes.py` content queries; `proxies.py` proxy endpoints; `status.py` health/readiness/version; `tasks.py` task endpoints.

## Schemas (4/4)

`service/schemas/__init__.py` DTO facade; `accounts.py` account/candidate requests; `proxies.py` proxy requests; `tasks.py` provider-aware task requests.

## Services (6/6)

`service/services/__init__.py` marker; `account_service.py` accounts/QR/candidates; `export_service.py` workbook/image export; `note_service.py` raw content queries; `proxy_service.py` proxy workflows/check; `task_service.py` admission/dedupe/resume.

## Static Frontend (3/3)

`service/static/app.js` user-owned API/state/render/events; `index.html` user-owned console DOM; `styles.css` user-owned presentation.

## Content Store (3/3)

`store/__init__.py` marker; `store/xhs/__init__.py` compatibility mapping/factory; `store/xhs/_store_impl.py` SQLAlchemy partial upserts/attribution.

## Tests (26/26)

`tests/test_app_lifespan.py` lifecycle; `test_content_repository.py` content schema/upserts; `test_justoneapi_executor.py` remote execution; `test_justoneapi_provider.py` transport/policy; `test_local_executor.py` lease propagation; `test_qr_sessions.py` QR cleanup; `test_redaction.py` secret boundaries; `test_runtime_env.py` env parsing; `test_service_db_tasks.py` operational persistence; `test_startup_config.py` bootstrap order; `test_supervisor_windows.py` supervision; `test_task_manager_providers.py` provider queues; `test_task_service_providers.py` task use cases; `test_xhs_comment_replies.py` reply option behavior.

## Tools (10/10)

`tools/README.md` guide; `tools/__init__.py` marker; `crawler_util.py` browser/cookie/URL helpers; `create_search_tasks.py` submission CLI; `export_note_comments_md.py` Markdown export CLI; `httpx_util.py` client factory; `redaction.py` central masking; `sync_comments_to_dwd.py` MySQL ETL; `time_util.py` time helpers; `utils.py` logging/CLI compatibility.

## Run-Owned Paths

The run root, `discovery/`, `discovery/agent-reports/`, `target/`, `target/agent-reports/`, `current/`, `iterations/`, and `final/` are durable workflow directories. Current files are `run-state.md`, C1-C5, this manifest, `current-state.md`, and `open-questions.md`.

## Metadata-Only Exclusions

`.git/` VCS; `.idea/` IDE; `.venv/` generated broken environment; every `__pycache__/` bytecode; `.env` secret configuration; `RUNTIME_DO_NOT_READ.md` protected contents; `browser_data/` account profiles; `data/` operational state; `exports/` generated business output; SQLite DB/WAL/SHM files active persistence. Future logs, credentials, uploads, backups, nested repos, node modules, dist/build, and test/type caches receive the same exact-path classification when present. Root `cache/` is explicitly included source.

Coverage result: `130/130`, no duplicate tracked path, no tracked symlink/submodule.

## Cycle 0001 Coverage Reconciliation

The baseline inventory above remains unchanged. The accepted cycle added one
in-scope project path: `tests/test_config_contract.py`, owned by tests and used
to enforce configuration/sample/documentation and artifact-exclusion parity.
Current coverage is therefore `131/131` project paths with zero exact-path
omissions. No path was moved or deleted, and all exclusions retain their prior
classification.

Cycle 0002 added `tests/test_dependency_contract.py`, owned by tests and used to
enforce direct-dependency manifest parity. Current coverage is `132/132` project
paths with zero exact-path omissions. No path was moved or deleted.

Cycle 0003 added five in-scope project paths: `tests/test_runtime_lock.py`,
`tests/test_image_downloader.py`, `tests/test_proxy_config.py`,
`tests/test_verification.py`, and `tools/verify.py`. They characterize runtime
locking, image downloads, proxy normalization/masking, and the unified
verification entry point. Current coverage is `137/137` project paths with zero
exact-path omissions. No path was moved or deleted, and all exclusions retain
their prior classification.

Cycle 0004 added three in-scope project paths:
`tests/test_frontend_contract.py`, `tests/test_export_service_contract.py`, and
`tests/test_architecture_contract.py`. They characterize static frontend/API
coupling, export behavior, and facade/provider/route dependency boundaries.
Current coverage is `140/140` project paths with zero exact-path omissions. No
path was moved or deleted.

Cycle 0005 added three in-scope project paths:
`tests/test_account_service_contract.py`, `tests/test_account_pool_contract.py`,
and `tests/test_diagnostic_redaction_contract.py`. They characterize account
orchestration, pool lifecycle/isolation, and diagnostic redaction. Current
coverage is `143/143` project paths with zero exact-path omissions. No path was
moved or deleted.

Cycle 0006 added three in-scope project paths: `service/repositories/__init__.py`,
`service/repositories/accounts.py`, and `tests/test_account_repository_contract.py`.
They establish the injectable account persistence ownership boundary and its
contract. Current coverage is `146/146` project paths with zero exact-path
omissions. No path was moved or deleted.

Cycle 0007 added `tests/test_runtime_composition_contract.py`, owned by tests and
used to characterize runtime construction, application composition, lifecycle,
failure, and isolation behavior. Current coverage is `147/147` project paths
with zero exact-path omissions. No path was moved or deleted.

Cycle 0008 added `service/repositories/proxies.py` and
`tests/test_proxy_repository_contract.py`. They establish and characterize the
proxy-management persistence boundary. Current coverage is `149/149` project
paths with zero exact-path omissions. No path was moved or deleted.

## Exact Canonical Path Index

Each entry resolves to the substantive ownership/function record in its section above:

- `.env.example`
- `.gitignore`
- `.python-version`
- `LICENSE`
- `README.md`
- `RUNTIME_DO_NOT_READ.md`
- `base/__init__.py`
- `base/base_crawler.py`
- `cache/__init__.py`
- `cache/local_cache.py`
- `config/README.md`
- `config/__init__.py`
- `config/base_config.py`
- `config/db_config.py`
- `config/settings.py`
- `config/xhs_config.py`
- `database/__init__.py`
- `database/db_session.py`
- `database/models.py`
- `docs/README.md`
- `docs/ai-change-guide.md`
- `docs/api.md`
- `docs/architecture.md`
- `docs/config.md`
- `docs/frontend.md`
- `docs/mysql-ai-platform.md`
- `docs/project-map.md`
- `docs/task-lifecycle.md`
- `docs/technical-debt.md`
- `docs/testing.md`
- `libs/stealth.min.js`
- `media_platform/__init__.py`
- `media_platform/xhs/__init__.py`
- `media_platform/xhs/client.py`
- `media_platform/xhs/exception.py`
- `media_platform/xhs/extractor.py`
- `media_platform/xhs/field.py`
- `media_platform/xhs/help.py`
- `media_platform/xhs/login.py`
- `media_platform/xhs/playwright_sign.py`
- `media_platform/xhs/xhs_sign.py`
- `model/__init__.py`
- `model/m_xiaohongshu.py`
- `ops/README.md`
- `ops/import_xhs_cookie_file.ps1`
- `ops/start-windows-foreground.cmd`
- `ops/supervisor_windows.py`
- `pyproject.toml`
- `requirements.txt`
- `service/README.md`
- `service/__init__.py`
- `service/account_pool.py`
- `service/app.py`
- `service/circuit_breaker.py`
- `service/crawler_engine.py`
- `service/dependencies.py`
- `service/domain/__init__.py`
- `service/domain/crawl_result.py`
- `service/domain/xhs_content.py`
- `service/executors/__init__.py`
- `service/executors/base.py`
- `service/executors/justoneapi.py`
- `service/executors/local.py`
- `service/executors/registry.py`
- `service/image_downloader.py`
- `service/main.py`
- `service/providers/__init__.py`
- `service/providers/justoneapi/__init__.py`
- `service/providers/justoneapi/client.py`
- `service/providers/justoneapi/errors.py`
- `service/providers/justoneapi/models.py`
- `service/providers/justoneapi/normalizer.py`
- `service/providers/justoneapi/options.py`
- `service/repositories/__init__.py`
- `service/repositories/accounts.py`
- `service/repositories/proxies.py`
- `service/proxy_config.py`
- `service/rate_limiter.py`
- `service/routes/__init__.py`
- `service/routes/accounts.py`
- `service/routes/export.py`
- `service/routes/login.py`
- `service/routes/notes.py`
- `service/routes/proxies.py`
- `service/routes/status.py`
- `service/routes/tasks.py`
- `service/runtime_env.py`
- `service/runtime_lock.py`
- `service/schemas/__init__.py`
- `service/schemas/accounts.py`
- `service/schemas/proxies.py`
- `service/schemas/tasks.py`
- `service/service_db.py`
- `service/services/__init__.py`
- `service/services/account_service.py`
- `service/services/export_service.py`
- `service/services/note_service.py`
- `service/services/proxy_service.py`
- `service/services/task_service.py`
- `service/static/README.md`
- `service/static/app.js`
- `service/static/index.html`
- `service/static/styles.css`
- `service/task_manager.py`
- `start_xhs_service.py`
- `store/__init__.py`
- `store/xhs/__init__.py`
- `store/xhs/_store_impl.py`
- `tests/test_account_pool_contract.py`
- `tests/test_account_repository_contract.py`
- `tests/test_account_service_contract.py`
- `tests/test_app_lifespan.py`
- `tests/test_architecture_contract.py`
- `tests/test_content_repository.py`
- `tests/test_config_contract.py`
- `tests/test_dependency_contract.py`
- `tests/test_diagnostic_redaction_contract.py`
- `tests/test_export_service_contract.py`
- `tests/test_frontend_contract.py`
- `tests/test_justoneapi_executor.py`
- `tests/test_justoneapi_provider.py`
- `tests/test_local_executor.py`
- `tests/test_qr_sessions.py`
- `tests/test_redaction.py`
- `tests/test_runtime_env.py`
- `tests/test_runtime_lock.py`
- `tests/test_runtime_composition_contract.py`
- `tests/test_image_downloader.py`
- `tests/test_proxy_config.py`
- `tests/test_proxy_repository_contract.py`
- `tests/test_service_db_tasks.py`
- `tests/test_startup_config.py`
- `tests/test_supervisor_windows.py`
- `tests/test_task_manager_providers.py`
- `tests/test_task_service_providers.py`
- `tests/test_verification.py`
- `tests/test_xhs_comment_replies.py`
- `tools/README.md`
- `tools/__init__.py`
- `tools/crawler_util.py`
- `tools/create_search_tasks.py`
- `tools/export_note_comments_md.py`
- `tools/httpx_util.py`
- `tools/redaction.py`
- `tools/sync_comments_to_dwd.py`
- `tools/time_util.py`
- `tools/utils.py`
- `tools/verify.py`
- `var.py`
