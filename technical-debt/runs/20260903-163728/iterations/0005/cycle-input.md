# Cycle 0005 Input

## Live Baseline

- Snapshot: `2026-09-04 09:52:42 +08:00`; branch `dev`, HEAD
  `f7f99aeff476c3cbe2959cbc69130a02918c57ce`, index empty.
- Coverage: 140/140 project paths, comprising 130 tracked baseline paths and
  ten accepted test/tool paths; no exact-path omission.
- Accepted cycles: configuration parity, dependency export parity,
  runtime/image/proxy/verifier characterization, and frontend/export/
  architecture contracts.
- Goals: 3 `UNSATISFIED`, 6 `PARTIAL`, 2 `BLOCKED`.

## Current Gates And Dependencies

- New Cycle 0004 contracts: 16/16; combined focused suite: 50/50.
- `python -B -m tools.verify` runs all phases and returns 1 because broad
  discovery is 82 outcomes, 71 passes, 10 import errors, and 1 dependent
  failure. The accepted missing modules remain only `sqlalchemy`, `aiosqlite`,
  and `playwright`.
- Runtime dependency declarations/direction remain unchanged. All accepted new
  paths are tests or a standard-library verification orchestrator.
- `git diff --check`, scope, empty index, and user/pinned hashes pass.

## Ownership And Authority

- User-owned read-only: `service/runtime_lock.py` and the three
  `service/static/` files at their recorded hashes.
- Protected metadata-only: `.env`, `RUNTIME_DO_NOT_READ.md`, databases, browser
  profiles, exports, uploads/backups, credentials, and secret environment
  values. Generated/excluded roots retain prior classifications.
- No install/network/resolver, real DB/browser/proxy, protected-content access,
  migration, product/security/deployment decision, commit, push, or deployment
  is authorized.
- `TD-009/010` blocked portions and unevidenced resource thresholds remain out
  of scope. Missing dependencies limit direct lifecycle/persistence execution;
  analysts must distinguish safe isolated characterization from unverifiable
  production refactors.

## Wave A Assignment

Reinspect the live repository and every `UNSATISFIED`/`PARTIAL` goal. Propose
the largest coherent ready batch using fresh evidence, with affected paths and
callers, goal IDs, invariant, dependencies, exact hermetic oracle, recovery
class, risk/confidence, and authority/product boundaries. Challenge whether
additional characterization is still valuable or whether remaining independent
work is genuinely blocked. Do not reuse Cycle 0004 rankings and do not write.
