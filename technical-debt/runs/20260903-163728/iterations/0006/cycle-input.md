# Cycle 0006 Input

## Live Baseline

- Snapshot: `2026-09-04 12:03:43 +08:00`; branch `dev`, HEAD `f7f99aeff476c3cbe2959cbc69130a02918c57ce`, index empty.
- Coverage: 143/143 project paths, comprising 130 tracked baseline paths and thirteen accepted test/tool paths; no exact-path omission.
- Accepted cycles now include account lifecycle contracts and two narrow diagnostic repairs.
- Goals: 3 `UNSATISFIED`, 6 `PARTIAL`, 2 `BLOCKED`.

## Current Gates And Dependencies

- Cycle 0005 new contracts: 14/14; combined focused suite: 64/64.
- Broad discovery is 96 outcomes, 85 passes, 10 import errors, and 1 dependent failure. Missing modules remain only `sqlalchemy`, `aiosqlite`, and `playwright`.
- Runtime dependency direction changed only by the already-established `service -> tools.redaction` edge; no external package or cycle was added.
- Compile, diff, scope, empty-index, recovery, and user-hash gates pass.

## Ownership And Authority

- User-owned read-only: `service/runtime_lock.py` and the three `service/static/` files at their recorded hashes.
- Protected content and generated/runtime roots retain prior metadata-only classifications.
- No install/network/resolver, real database/browser/proxy, protected-content access, migration, product/security/deployment decision, commit, push, or deployment is authorized.
- Missing dependencies still limit direct lifecycle/persistence execution; distinguish isolated evidence from verifiable production work.

## Wave A Assignment

Reinspect the live repository and every `UNSATISFIED`/`PARTIAL` goal. Propose the largest coherent authorized batch using fresh evidence, with affected paths/callers, goal IDs, invariant, dependencies, exact hermetic oracle, recovery class, risk/confidence, and product boundaries. Identify whether the new account contracts unlock a safe structural change, but reject changes that cannot be verified without missing dependencies. Do not reuse Cycle 0005 rankings and do not write.
