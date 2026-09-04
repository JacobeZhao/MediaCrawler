# C1 Structure And Ownership

## Scope And Evidence

- Read-only mapping of `E:/project/MediaCrawler` at `f7f99aeff476c3cbe2959cbc69130a02918c57ce`.
- Evidence: `git ls-files`, `git status`, recursive path metadata, imports/callers, ordinary source/docs/config/tests, and run-owned state.
- Protected contents were not opened. The four pre-existing modified `service/` files were inspected read-only and remain `USER_OWNED`.
- Confidence is high for tracked structure and static ownership; runtime/external behavior remains unverified.

## Complete Ownership Map

The 130 tracked files divide into root metadata/entry points (10), `base/` (2), `cache/` (2), `config/` (6), `database/` (3), `docs/` (11), `libs/` (1), `media_platform/` (10), `model/` (2), `ops/` (4), `service/` (52), `store/` (3), `tests/` (14), and `tools/` (10). Every tracked file was inspected or classified; package markers have import-compatibility ownership and each test maps to the named subsystem it characterizes. The canonical per-path reconciliation is retained in `../coverage-manifest.md`.

| Boundary | Responsibility and grouping | Consumers / assessment |
| --- | --- | --- |
| root | packaging, launch, licensing, context variables, repository docs | `start_xhs_service.py` is the executable entry; `var.py` is a generic root-level ambient-context bridge |
| `service/` | FastAPI composition, routes, schemas, workflows, queues, provider execution, local crawler, static console | canonical application home, but several coordinators mix independent responsibilities |
| `media_platform/xhs/` | XHS transport, login, extraction, signing, protocol values/errors | canonical local-platform adapter; private upstream drift remains unknown |
| `database/` + `store/xhs/` | content schema/session plus mapping/upsert repository | valid two-layer split, but runtime DB output is colocated with source and query ownership crosses into services |
| `config/` | typed settings plus legacy compatibility globals | canonical settings coexist with wildcard mutable compatibility exports |
| `base/`, `model/`, `cache/` | inherited contracts, XHS URL DTOs, live expiring login cache | active compatibility source; names are generic and easily mistaken for framework/generated content |
| `tools/` | imported production helpers plus standalone operator/data CLIs | mixed library/operations ownership; redaction and time utilities are production dependencies |
| `ops/` | Windows startup, supervision, log rotation, account import | canonical operator boundary |
| `tests/` | 14 regression/characterization modules | grouped by lifecycle, configuration, providers, persistence, QR, redaction, and supervisor behavior |
| `docs/` | architecture, API, task, frontend, config, testing, debt, MySQL context | canonical maintainer documentation; durable run artifacts are a separate run-owned subtree |
| `libs/` | vendored minified Playwright stealth asset | direct runtime consumer exists; exact provenance/version is not recorded |

## Structural Findings

1. Upstream MediaCrawler packages and the newer layered `service/` architecture coexist; cross-boundary compatibility imports are active, not dead code.
2. `cache/` is tracked live source (`cache/local_cache.py` is imported by XHS login), correcting the initial generated-root classification.
3. Persistence spans `database/`, `store/xhs/`, and `service/service_db.py`; two SQLite databases are intentional, but names and cross-store queries obscure ownership.
4. Models live in four distinct but poorly signposted homes: `model/`, `service/domain/`, `service/schemas/`, and provider transport models.
5. Responsibility concentration is directly evidenced in `service/crawler_engine.py`, `service/service_db.py`, `service/task_manager.py`, `service/executors/justoneapi.py`, and static `app.js`.
6. `database/sqlite_tables.db` is runtime output colocated with Python source.
7. Configuration parsers/constants and dependency declarations are duplicated; no lockfile or parity gate exists.
8. Public package intent varies between empty markers, wildcard exports, lazy exports, and implementation-heavy `__init__.py` files.
9. Documentation/source contains visible encoding-risk text that requires byte/encoding verification before calling it corruption.
10. Version ownership conflicts: package metadata says `0.1.0`, runtime/OpenAPI/settings say `1.0.0`; choosing a value is a product/release decision.

## Exclusions And Unknowns

Metadata-only: `.git/`, `.idea/`, `.venv/`, all `__pycache__/`, `browser_data/`, `data/`, `exports/`, SQLite files/sidecars, `.env`, `RUNTIME_DO_NOT_READ.md`, and any future credentials/backups/uploads/generated output. No top-level links or submodules were found. No CI/release owner, live external contract, runtime database contents, or supported public Python API list was established.

Status: `COMPLETE_WITH_CORRECTION`; include tracked root `cache/` as ordinary source.
