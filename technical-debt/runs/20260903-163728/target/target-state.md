# Immutable Initial Target State

## Target Shape

Incrementally harden the existing single-process FastAPI architecture. Retain current root/package layout and public compatibility facades. Routes own HTTP translation; services own framework-neutral use cases; executors remain provider-isolated; runtime construction occurs only in lifespan through an explicit container; operational and content persistence each have one physical-schema boundary. Move no runtime data and change no public behavior without an evidenced decision.

Canonical homes remain: root bootstrap/metadata; `service/routes`, `schemas`, `services`, `domain`, `executors`, `providers`, `static`; `media_platform/xhs` protocol/browser integration; `database` content schema/repository; `service` operational persistence behind `service_db`; `config` typed settings plus legacy projections; `tools` production helpers and operator CLIs until individual moves prove value; `ops`, `tests`, and `docs`. Compatibility modules remain thin and documented. Generated/protected/runtime paths remain excluded.

## Original Goals

### `TD-001` Reproducible Verification

- Invariant: one canonical direct dependency declaration, checked compatibility export, lock resolution, and one local/CI hermetic verification entry point.
- Oracle: a clean supported-Python environment collects all 91 declared tests without dependency import errors; manifest/lock parity, compileall, and full unittest discovery pass through the same command.
- Constraints: no bundled dependency upgrades; installation/network requires separate execution authority.
- Priority/status: P0 `UNSATISFIED`.

### `TD-002` Behavior Characterization

- Invariant: structural edits are preceded by deterministic coverage of HTTP contracts, runtime-lock contention, proxy flows, image/export limits, account transitions, frontend DOM/API coupling, and affected crawler behavior.
- Oracle: focused tests exist for each boundary, preserve all current public/task/provider behavior, and pass with the broad hermetic gate.
- Dependencies: `TD-001`.
- Priority/status: P0 `PARTIAL`.

### `TD-003` Explicit Runtime Composition

- Invariant: importing app/dependency modules creates no browser/client/queue/directory and mutates no compatibility config; lifespan owns exactly one process container.
- Oracle: isolated import and lifecycle tests prove no import side effects and ordered exactly-once start/stop while `service.app:app`, accessors, and configuration precedence remain compatible.
- Dependencies: startup characterization in `TD-002`; recovery R1.
- Priority/status: P0 `UNSATISFIED`.

### `TD-004` Operational Persistence Ownership

- Invariant: task/audit, account/candidate, proxy, tag/event operations have narrow repository ownership behind the existing `service_db` facade.
- Oracle: callers can inject temporary repositories; no task manager/executor contract imports concrete SQL; existing dictionaries, statuses, schema, paths, leases, checkpoints, retries, and audits are unchanged.
- Dependencies: `TD-001`, persistence characterization; recovery R1.
- Priority/status: P1 `UNSATISFIED`.

### `TD-005` Content Persistence Ownership

- Invariant: content reads, writes, counts, attribution, and export queries cross one repository boundary; raw content SQL does not live in application services or operational persistence.
- Oracle: static SQL boundary check plus note/comment/creator/count/export/upsert/attribution contracts produce identical results with unchanged schema/path/row shapes.
- Dependencies: `TD-002`, `TD-004`; recovery R1.
- Priority/status: P1 `UNSATISFIED`.

### `TD-006` Explicit Attribution And Provider Isolation

- Invariant: content attribution is explicit and cannot leak across concurrent tasks; providers share only executor/content contracts and canonical records.
- Oracle: concurrency tests prove keyword/provider/task isolation; `var.py` is confined to a compatibility adapter; dependency tests reject local/remote infrastructure cross-edges.
- Dependencies: `TD-005`; preserve provider identity/options/queues/checkpoints/budgets; recovery R1.
- Priority/status: P1 `PARTIAL`.

### `TD-007` Configuration And Artifact Parity

- Invariant: every environment input is typed and synchronized with non-secret sample/docs; deployment exclusions and compatibility surfaces are mechanically documented.
- Oracle: settings/sample/docs parity and deployment-manifest checks pass, retain tracked `cache/*.py`, and exclude exact protected/runtime/generated paths; public import manifest has smoke tests.
- Constraints: preserve names/defaults/precedence and unknown external imports; recovery R1.
- Priority/status: P0 `PARTIAL`.

### `TD-008` Bounded Safe Resource Handling

- Invariant: image/export fetching has characterized scheme, redirect, timeout, byte, content-type, decode, concurrency, and atomic-write bounds without changing valid output.
- Oracle: deterministic fixtures reject invalid/oversized/partial inputs and preserve valid HTTPS image/export behavior; no partial cache files remain.
- Constraints: destination allow/deny policy is not changed without a product/security decision; recovery R1.
- Priority/status: P0 `UNSATISFIED`.

### `TD-009` Auditable Schema Evolution

- Invariant: future schema evolution is ordered, transactional, repeatable, versioned, and recoverable rather than hidden in CRUD/startup.
- Oracle: fresh/legacy/interrupted temporary DB fixtures converge idempotently with recorded migration IDs and pre/post/restore oracles.
- Constraints: duplicate survivor policy and any real protected DB action require product approval and R2 recovery.
- Priority/status: P0 `BLOCKED` for real-data policy; authorized fixture/runner preparation may proceed.

### `TD-010` Explicit Security And Release Decisions

- Invariant: candidate secret projection, endpoint authentication/CORS/listener trust, at-rest encryption, outbound destination policy, and canonical version are governed by explicit decision records before behavior changes.
- Oracle: each item has an approved retain/change decision and, if changed, corresponding HTTP/network/version tests; until then current behavior is documented and no silent change occurs.
- Constraints: product/security/deployment authority required; no secret/protected inspection.
- Priority/status: P0 `BLOCKED`.

### `TD-011` Recovery-Governed Incremental Maintenance

- Invariant: high-risk modules change one characterized responsibility per batch and every batch records preimage, allowlist, R-class, focused/broad gates, and restore recipe.
- Oracle: cycle artifacts prove scope, recovery, unchanged user/protected paths, and no unsupported compatibility removal.
- Priority/status: P0 `PARTIAL`.

## Completion Boundary

No directory churn, optional tool adoption, external probe, deployment, or product decision is implied. Blocked goals prevent `COMPLETE` but do not stop independent authorized goals. This target text is immutable; later interpretation changes require dated addenda.
