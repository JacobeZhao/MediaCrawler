# Cycle 0004 Input

## Live Baseline

- Snapshot time: `2026-09-04 09:05:11 +08:00`.
- Branch/revision: `dev` at
  `f7f99aeff476c3cbe2959cbc69130a02918c57ce`; index empty.
- Coverage: 137/137 project paths: 130 tracked baseline paths plus seven
  accepted test/tool paths from Cycles 0001-0003; zero exact-path omissions.
- Accepted cycles: 0001 configuration parity, 0002 dependency export parity,
  0003 runtime-lock/image/proxy characterization and unified verification.
- Goals: 3 `UNSATISFIED`, 6 `PARTIAL`, 2 `BLOCKED`.

## Ownership And Boundaries

- `USER_OWNED`: `service/runtime_lock.py`, `service/static/app.js`,
  `service/static/index.html`, `service/static/styles.css`; their recorded
  SHA-256 values remain unchanged.
- `RUN_OWNED`: accepted `.env.example`, `docs/config.md`, `docs/testing.md`,
  `docs/ai-change-guide.md`, `requirements.txt`, `tools/README.md`, seven new
  test/tool paths, and `technical-debt/**`.
- Protected metadata only: `.env`, `RUNTIME_DO_NOT_READ.md`, databases, browser
  profiles, exports, uploads/backups, credentials, and secret environment
  content.
- Excluded/generated metadata only: `.git/`, `.idea/`, `.venv/`, bytecode and
  test caches, `node_modules/`, `dist/`, `build/`, runtime `data/`,
  `browser_data/`, and `exports/`. Root `cache/` remains included source.
- No install, network, real database/browser/proxy operation, protected-content
  access, commit, push, deployment, migration, or product/security decision is
  authorized.

## Current Verification

- Combined focused suites: 34/34 pass.
- `python -m tools.verify`: dependency/configuration contracts and compileall
  pass; it runs full discovery and returns 1 honestly.
- Full discovery: 66 outcomes, 55 pass, 10 import errors, 1 dependent failure.
  The accepted environment fingerprint is missing `sqlalchemy`, `aiosqlite`,
  and `playwright` only.
- `git diff --check` passes. HEAD, index, scope, and user-owned hashes show no
  drift after Cycle 0003.

## Live Gap

- `TD-003`, `TD-004`, `TD-005`: `UNSATISFIED`.
- `TD-001`, `TD-002`, `TD-006`, `TD-007`, `TD-008`, `TD-011`: `PARTIAL`.
- `TD-009`, `TD-010`: `BLOCKED` on product/security/deployment decisions or R2
  evidence; do not select their blocked portions.
- Runtime dependency direction remains unchanged. Cycle 0003 added only
  standard-library tests and a standard-library subprocess verifier; no
  external edge or cycle was introduced.

## Wave A Assignment

Using the live tree, immutable target, migration constraints, goal matrix,
dependency index, and this snapshot, propose the largest coherent ready batch.
Every candidate must cite affected paths/callers, goal IDs, intended invariant,
dependencies, exact verification oracle, recovery class, risk, confidence, and
any authority/product boundary. Do not reuse stale Cycle 0003 rankings and do
not write repository files.
