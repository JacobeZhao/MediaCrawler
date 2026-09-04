# Cycle 0007 Execution Plan

## Decision And Invariant

Create one dependency-free runtime composition characterization file before any production container migration. The batch records the current construction graph, application facade/shape, import and filesystem events, and lifecycle success/failure semantics without endorsing import-time side effects as the target architecture.

The planning reports all returned `PASS`. Their only dissent was grouping: P1 proposed nine parent tests, P2 eight, and P3 seven. Adopt eight to keep enabled, disabled, normal teardown, startup failure, and cleanup failure independently diagnosable while grouping the application shape and root branches into one isolated application scenario.

## Authority, Writer, And Allowlist

- E1 is the sole code writer.
- Code allowlist: create the complete new file `tests/test_runtime_composition_contract.py` only.
- E2 and E3 are read-only and run after E1 finishes.
- `service/main.py`, `service/app.py`, `service/dependencies.py`, all existing tests, and every other product path are read-only.
- No install, network, real DB/browser/proxy/worker, protected/default runtime path, product decision, commit, push, or deployment.

## Checkpoint C1: Isolated Contract File

Recovery is `R1 Exact Preimage`. The target is absent, untracked, and unstaged at HEAD `f7f99aeff476c3cbe2959cbc69130a02918c57ce`. Recovery removes only this attributed complete new file with a narrow patch; it never uses checkout/reset or changes the index.

Implement exactly eight `unittest` parent tests:

1. Current dependency graph constructs once, preserves necessary injected/shared identities, returns identical instances from all eight accessors, and projects the three compatibility config values.
2. `service.app:app` creation plus title/version/lifespan, CORS, seven-router order, image/static mounts, root file/fallback branches, and current import/filesystem events.
3. Disabled startup order and omission of local engine/pool starts.
4. Enabled startup order through body entry.
5. Normal teardown order and runtime-lock identity/release.
6. Pre-yield failure matrix, including the no-cleanup lock boundary and complete cleanup after later failures.
7. Cleanup continuation, `BaseException` handling, release, first-error rule, and body/startup error precedence.
8. Explicit isolation audit: config/import filesystem events stay in the temporary root and forbidden real infrastructure modules/paths are untouched.

Each parent runs a bounded child with synthetic leaf modules and one structured `RESULT=` record. Use a temporary cwd, absolute empty `XHS_ENV_FILE`, temporary pycache/home/profile/temp/runtime paths, `-B`, `shell=False`, a finite timeout, and a minimal non-secret environment. The parent must not import the runtime targets and must retain its modules, environment, and cwd. Assertions target observable calls, identities, order, response branches, and paths rather than implementation text or private framework structure.

Focused oracle: the new file passes `8/8` and the established focused set passes `77/77`.

## Batch Gates

1. `python -B -m unittest discover -s tests -p test_runtime_composition_contract.py -v`
2. Existing accepted focused files plus the new file: `77/77`.
3. `python -B -m compileall -q service config media_platform store database tools base cache model start_xhs_service.py`
4. `git diff --check` and exact path/index/status checks.
5. `python -B -m tools.verify` and direct full discovery.
6. Broad expected total: `109 outcomes / 98 pass / 10 errors / 1 failure`; non-passing results must have only the accepted missing `sqlalchemy`, `aiosqlite`, and `playwright` fingerprint.
7. Confirm coverage `147/147`, new-file encoding/newline/hash, and unchanged four user-owned hashes.
8. Independent E2 behavior/verification and E3 architecture/scope verdicts must both be `PASS`.

One repair attempt is reserved inside the cycle allowance. Any new failure, timeout, real infrastructure/default-path access, parent-process pollution, scope expansion, or baseline-fingerprint drift is `REVISE`; production edits or additional authority requirements are `BLOCK`. Three failed coherent write-and-gate attempts trigger exact recovery and `BLOCKED_TECHNICAL` for this batch.

## Target Effect

On acceptance, `TD-002`, `TD-007`, and `TD-011` gain current evidence. `TD-003` remains `UNSATISFIED`, but its separately recoverable production migration becomes ready. Proxy repository extraction remains the next production candidate.
