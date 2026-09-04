# Cycle 0003 Input

- HEAD `f7f99aeff476c3cbe2959cbc69130a02918c57ce`, branch `dev`, index empty.
- Current coverage: 132/132 project paths, 130 baseline tracked plus two
  accepted tests; zero exact omissions.
- Accepted run-owned product paths: `.env.example`, `docs/config.md`,
  `docs/testing.md`, `requirements.txt`, `tests/test_config_contract.py`, and
  `tests/test_dependency_contract.py`; durable run docs are run-owned.
- Four user-owned paths/hashes remain exactly as recorded; they are read-only.
- Protected/excluded boundaries and prohibited external actions are unchanged.
- Runtime imports and dependency values are unchanged. Direct dependency
  manifests now have a passing exact export contract.
- Latest gates: dependency 3/3, config 3/3, runtime-env 14/14, compileall and
  diff-check pass; broad fallback is 52 outcomes with 41 pass and the same 10
  dependency import errors plus 1 dependent failure from unavailable
  SQLAlchemy, aiosqlite, and Playwright.
- Goals: 4 `UNSATISFIED`, 5 `PARTIAL`, 2 `BLOCKED`. Cycles 0001 and 0002
  advanced configuration parity, dependency parity, and recovery governance.
- Stale evidence: all prior cycle candidate rankings/plans are stale for batch
  selection. Immutable target and refreshed ownership/coverage/dependency/gate
  evidence remain valid.
- Authorized scope: reversible repository-local cleanup and hermetic tests that
  preserve behavior. No user-owned hunk edits, install/network, real DB,
  protected content, product/security decision, lock generation, commit, push,
  or deployment.
- Required wave: exactly three new independent read-only A1-A3 analyses. Recheck
  every open goal and recommend the smallest coherent ready batch with paths,
  callers, invariant, dependencies, oracle, recovery, risk, and confidence.
