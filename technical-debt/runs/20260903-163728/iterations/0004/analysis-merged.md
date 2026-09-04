# Cycle 0004 Analysis Merge

## Evidence Decision

All three analyses confirm the `TD-003/004/005` gaps, but they do not establish
a safe production rewrite in the current environment. Runtime composition would
change every accessor and lifecycle edge while its dependency-backed tests do
not collect. Persistence and attribution changes require temporary repository
and query-shape coverage first. These candidates are deferred, not rejected as
targets.

Image resource enforcement is also deferred. The target requires bounded safe
handling, but the repository supplies no evidenced byte, pixel, decode, or
concurrency thresholds. Selecting values now would change valid/invalid product
behavior. Destination policy remains explicitly blocked. Cycle 0003
characterization is retained as the basis for a later evidence-backed decision.

## Accepted Largest Compatible Batch

Select three ordered, independently recoverable, test-only checkpoints:

1. Frontend DOM/API/reference characterization in new
   `tests/test_frontend_contract.py`, with all user-owned static files read-only
   and hash-pinned. Goals: `TD-002`, `TD-007`, `TD-011`.
2. Export image/cache/limit/failure characterization in new
   `tests/test_export_service_contract.py`, using explicit temporary paths,
   standard-library mocks/doubles, no real DB/network, and isolated handling of
   the unavailable `aiosqlite` import. Goals: `TD-002`, `TD-008`, `TD-011` and
   prerequisite evidence for `TD-005`.
3. Compatibility-facade and provider dependency-direction characterization in
   new `tests/test_architecture_contract.py`, using AST/static inspection and
   only dependency-safe facade imports. Goals: `TD-006`, `TD-007`, `TD-011`.

These checkpoints share R1 absent-file recovery, low-to-medium risk,
standard-library hermetic verification, no production/public behavior change,
and the same accepted broad-failure boundary. Different focused oracles remain
independently observable and do not justify separate cycles.

## Planning Requirements

P1 must define exact manifests and parsing rules rather than tests that merely
reproduce source data. P2 must prove no network, default runtime path,
protected content, real database, or leaked module stub and must pin all
read-only/user-owned hashes. P3 must challenge lexical JS/path normalization,
unsupported public-API claims, FastAPI/import side effects, and whether export
testing can remain isolated without production edits.

The broad oracle is `66 + N` outcomes and `55 + N` passes for `N` new test
methods, with exactly the same 10 dependency import errors and 1 dependent
failure. No install, production edit, user-file edit, migration, resource
policy, commit, push, deployment, or external action is permitted.
