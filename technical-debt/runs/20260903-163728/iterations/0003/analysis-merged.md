# Cycle 0003 Analysis Merge

All analysts agree the next batch must be a dependency-free, test-only R1
characterization and that structural/runtime/persistence/policy changes are not
ready. A1/A3 recommend runtime-lock contention; A2 recommends image downloading.

The coordinator selects only runtime-lock characterization. Its behavior is
already an explicit startup contract in `docs/testing.md` and
`docs/task-lifecycle.md`, its exact caller is lifespan acquire/release, and it is
a direct prerequisite for later `TD-003` work. The image candidate is retained
for a later independent cycle.

Accepted candidate:

- Product allowlist for planning: new `tests/test_runtime_lock.py` only.
- Read-only evidence: user-owned `service/runtime_lock.py` at SHA-256
  `3894DF26CA11DE868A25B7DC8F99AD8AB30A693AFFB3DA9E73EAF582E606BF64`
  and lifespan/docs callers.
- Invariant: one process owns an explicit temporary lock; a contender fails with
  the current public error and cannot replace holder metadata; release permits
  reacquisition; repeated release is harmless.
- Oracle: standard-library subprocess with bounded handshakes/timeouts and
  `finally` cleanup, no default runtime path, focused test plus existing gates
  and exact broad baseline delta.
- Recovery: R1 new-file nonexistence. Risk low-medium, confidence high.
- Forbidden: implementation/user file edits, image tests, docs, default runtime
  path, dependencies, network, DB/protected content, product changes, commit,
  push, or deployment.

## Updated-Workflow Revision

The cleanup workflow changed after the original merge: cycles must now select
the largest compatible ready set rather than defaulting to one small finding.
The original single-test selection is superseded before E2/E3 acceptance.

The revised Cycle 0003 batch includes all compatible, dependency-free R1 work
identified by A1-A3 that shares the same local verification boundary:

1. retain the completed runtime-lock characterization checkpoint;
2. add image-downloader behavior characterization without production changes;
3. add pure proxy configuration characterization without production changes;
4. add a dependency-free unified verification entry point and its contract
   tests/documentation, without installing or resolving packages.

These checkpoints jointly advance `TD-001`, `TD-002`, `TD-008`, and `TD-011`.
They may be recovered independently, use no protected/runtime state, and share
standard-library focused tests, compile/whitespace checks, and the same broad
baseline attribution. Different invariants remain independently observable and
therefore do not justify separate cycles under the updated rule.

Still excluded: public-import policy, resource-bound enforcement, runtime
composition, persistence, attribution, migrations, dependency resolution,
security/release/destination decisions, user-owned edits, and external actions.
