# C2 Runtime And Product Flow

## Scope

Read-only static mapping at baseline revision. Protected/runtime content was not opened; user-modified files were inspected read-only. Confidence is high for static flow and medium for live XHS/JustOneAPI behavior.

## Runtime Topology

`start_xhs_service.py` loads configuration and launches Uvicorn -> `service.app` calls `service.main.create_app()` -> lifespan acquires a single-instance lock, initializes operational/content SQLite, optionally starts the Playwright engine/account pool, registers provider executors, and starts one queue/worker per provider. Routes delegate to services, `service_db`, and `TaskManager`; local execution uses account pool -> crawler engine -> XHS client, while JustOneAPI execution uses its HTTP client/normalizer. Both write the canonical content store.

## Product Workflows

- Tasks: HTTP/frontend/tool submission -> provider-aware validation/dedupe -> persisted pending task -> provider queue -> lease/heartbeat/checkpoint -> completed, paused, or failed.
- Local provider: circuit/rate protection -> healthy account -> signed XHS search/creator/note calls -> optional details/comments/images -> content persistence.
- JustOneAPI: HTTPS/token validation -> request budgets and audit rows -> normalize notes/comments/creators -> fine-grained checkpoints -> shared persistence. Unknown billed outcomes are not replayed.
- Accounts: cookie/QR acquisition -> isolated profile -> validation/adoption -> pool rotation/captcha/cooldown/health. Proxy CRUD masks public credentials and can perform an external IP check.
- Reads/export: bounded content queries, path-validated image listing, and XLSX export; export may fetch/cache remote images despite using GET.
- Frontend: one no-build console polls status/tasks/accounts/candidates/proxies every 10 seconds and performs all operator mutations through common API helpers.
- Operations: Windows foreground/supervisor launchers and account import; a separate MySQL ODS-to-DWD CLI is not service runtime.

## State And Side Effects

Task state is `pending -> running -> completed|failed|paused`; explicit resume retains provider/checkpoint and recrawl sets force/clears checkpoint. Account state is ready/captcha/cooling/invalid with sticky captcha semantics. Operational SQLite owns tasks/audits/accounts/proxies/candidates/events; content SQLite owns creators/notes/comments/attribution; browser profiles, images, network calls, logs, exports, and external MySQL are separate side-effect planes.

## File/Directory Coverage

All tracked runtime-relevant files were connected to behavior. Routes are the HTTP boundary; schemas validate requests; services own use cases; executors own provider task flows; provider modules own remote transport/normalization; domain modules own canonical records; `media_platform/xhs` owns local protocol behavior; `store/xhs` and `database` own content writes/schema; root compatibility packages remain active. Documentation, manifests, all 14 tests, frontend assets, ops scripts, and tool CLIs were classified by their runtime consumer. See `../coverage-manifest.md` for the canonical one-record-per-path table.

## Risks And Unknowns

Import-time global composition, single-process-only state, mixed persistence APIs, active legacy globals/context, incomplete provider-neutral local flow, ungenerated JS/API coupling, unauthenticated wildcard-CORS mutation routes, export-side network writes, live upstream drift, and separate MySQL configuration are evidenced. Protected runtime contents and live providers were not inspected.

Status: `COMPLETE_WITH_OPEN_QUESTIONS`.
