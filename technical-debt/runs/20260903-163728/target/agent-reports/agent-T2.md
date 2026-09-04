# T2 Application And Domain Architecture

## Target

`service.main` is the sole composition root and builds an explicit process container after environment loading. Routes own Pydantic/FastAPI translation; application services use framework-neutral commands/results/errors. `TaskManager` depends on narrow task persistence ports. Operational and content SQLite each have one adapter boundary; cross-store enrichment is application orchestration. Provider executors remain isolated behind existing contracts. Attribution becomes explicit while context variables remain a compatibility adapter. `XHSCrawlerEngine` remains a facade and is decomposed only behind focused tests.

## Candidate Goals

- `T2-G01` P0/UNSATISFIED: no import-time resource construction/config mutation. Oracle: isolated imports create no engines/clients/queues/directories or config mutation; lifespan proves ordered exactly-once lifecycle.
- `T2-G02` P0/UNSATISFIED: HTTP layer exclusively owns framework DTOs/status/responses. Oracle: AST boundary gate plus characterization of all 37 current HTTP operations.
- `T2-G03` P0/UNSATISFIED: task lifecycle depends on a narrow repository port. Oracle: fake repository injection, no concrete DB imports in manager/executor contracts, all lease/checkpoint/retry/provider tests pass.
- `T2-G04` P0/UNSATISFIED: each SQLite schema has one adapter boundary. Oracle: DB imports/SQL restricted to adapters; read/write/count/export/upsert/attribution contract tests and unchanged schema/path snapshot.
- `T2-G05` P1/PARTIAL: provider infrastructure remains isolated behind `TaskExecutor`. Oracle: dependency tests reject cross-provider edges and verify identical canonical persistence shapes with attribution.
- `T2-G06` P1/PARTIAL: attribution is explicit and concurrency-safe. Oracle: concurrent no-leak test and `var.py` imports confined to a compatibility adapter.
- `T2-G07` P0/BLOCKED: schema evolution uses an ordered auditable runner separate from CRUD. Oracle: fresh/legacy/idempotency tests with migration identifiers; real DB and duplicate-deletion work remains R2/product-authority blocked.
- `T2-G08` P0/PARTIAL: refactoring preserves documented HTTP and Python compatibility surfaces. Oracle: contract manifest, import smoke, HTTP characterization; removal requires consumer evidence.

## Ordering And Constraints

Characterize HTTP/Python surfaces; introduce application error mapping; replace import-time construction; introduce operational ports behind `service_db`; consolidate content persistence without schema changes; make attribution explicit; then decompose only independently tested responsibilities. Preserve single-process behavior, routes/payloads/status, provider identity/options/queues/checkpoints/budgets, DB paths/schema/data, Uvicorn entry, user-owned files, and legacy imports. Code uses R1; real data uses separately authorized R2.

Status: independent proposal complete; not adopted until T1-T5 reconciliation.
