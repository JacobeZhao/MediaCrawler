# Current Project Cleanliness Audit

## Overall Result

Three independent read-only reviews score the current repository at `63`, `56`, and `42`. The equal-weight composite is `54/100` (median `56`, observed range `42-63`). Verdict: `PARTIAL / NOT CLEAN` with high confidence.

The range reflects different weighting, not factual disagreement. All reviewers agree that governance and regression evidence improved materially, while architecture, complete verification, persistence, resource enforcement, and production security remain unfinished.

## What Is Clean

- Recursive scope is reconciled at 149/149 project paths; exclusions and protected paths are classified.
- All current dirty product paths are attributable to user-owned or accepted run-owned work; the index is empty and user-owned hashes remain stable.
- Eight cycles have exact allowlists, recovery evidence, focused/broad gates, and independent final reviews.
- Configuration/sample/docs and dependency-export parity have mechanical contracts.
- Focused hermetic coverage is 82/82 for the accepted boundaries.
- Runtime lock, lifecycle cleanup, provider separation, account/proxy injection, redaction, frontend coupling, and image/export current behavior have useful deterministic contracts.

## What Is Not Clean

### High

- The canonical verifier still exits 1: 114 outcomes comprise 103 passes, ten import errors, and one dependent failure because the environment lacks `sqlalchemy`, `aiosqlite`, and `playwright`. No lockfile, valid project venv, or CI success closes `TD-001`.
- `service/dependencies.py` still constructs the runtime graph and mutates compatibility config at import; `service.app:app` application construction triggers image-directory creation. Cycle 0007 characterizes rather than removes this debt.
- Operational/content persistence remains mixed. `service/service_db.py` is 1,351 lines, task/audit/tag/event callers retain concrete edges, and content SQL/attribution crosses crawler, store, service, and database layers.
- Production security/release decisions remain open: wildcard CORS, default all-interface binding, no route authentication boundary, plaintext credential persistence/projection, outbound destination policy, encryption, and canonical version.
- Startup duplicate-row reconciliation lacks a versioned migration ledger, preflight report, and approved real-data survivor/recovery policy.

### Medium

- Image/export flows lack complete scheme, redirect, byte, content-type, decode, concurrency, and destination enforcement; export cache publication can leave partial files.
- Large multi-owner modules remain: `service_db.py` 1,351 lines, `crawler_engine.py` 1,125, and `executors/justoneapi.py` 1,009.
- QR session ownership has no concurrent poll/cancel/adopt proof, and background task loops still use raw `traceback.print_exc()`.
- Most new evidence is isolated characterization with synthetic leaves. It is valuable for refactoring but not equivalent to real FastAPI/DB/browser/crawler integration.

### Low

- Historical target text retains its original 91-test oracle while the live count is 114; immutable history is valid, but live documents must remain authoritative.
- `var.py` contains visible mojibake comments.
- Cycle 0008's `Git blob` labels are content digests in Git blob format, not proof the objects exist in the ODB. External preimage recovery remains independently hash-verified.

## Goal Reconciliation

All three reviewers independently agree with the live matrix: `TD-001`, `TD-002`, `TD-004`, `TD-006`, `TD-007`, `TD-008`, and `TD-011` are `PARTIAL`; `TD-003` and `TD-005` are `UNSATISFIED`; `TD-009` and `TD-010` are `BLOCKED`. Therefore zero goals are currently `SATISFIED`, and cleanup completion cannot be claimed.

## Recommended Sequence

1. Atomic export-cache publication and no-partial-file failure contract: ready, narrow, policy-free, and directly reduces risk.
2. Characterize and extract task/audit/tag/event operational repository boundaries without moving SQL.
3. Establish content repository ownership, then remove ambient attribution with concurrency evidence.
4. Resolve accessor and legacy-singleton compatibility before the explicit lifespan container migration.
5. With separate authority, close dependency/lock/CI, real migration policy, and security/deployment decisions.

Cycle 0009 selects item 1 for planning. It must not bundle destination allow/deny policy, resource thresholds without evidence, runtime composition, persistence migration, or security decisions.
