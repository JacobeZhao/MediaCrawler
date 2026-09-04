# Cycle 0002 Input

- HEAD: `f7f99aeff476c3cbe2959cbc69130a02918c57ce`; branch `dev`; index empty.
- Current coverage: 131/131 project paths, comprising 130 baseline tracked paths
  and accepted new `tests/test_config_contract.py`; zero exact omissions.
- Accepted run-owned product paths: `.env.example`, `docs/config.md`, and
  `tests/test_config_contract.py`; durable run documentation is also run-owned.
- User-owned paths and hashes are unchanged:
  `service/runtime_lock.py=3894DF26CA11DE868A25B7DC8F99AD8AB30A693AFFB3DA9E73EAF582E606BF64`,
  `service/static/app.js=1AAB7DE4630BDFCA380E1EB28550AFBE64340026F0A4A919851F66A2947E307E`,
  `service/static/index.html=8F569D97C1471E539050A0C2EC9E4ADBB516E88DD1E71155DBD3F1AD8D072CB6`,
  and `service/static/styles.css=130F506671FF1FF313A9F8916FC863082A3F00C36FE772B30332EA69233EDDB0`.
- Protected/excluded boundaries are unchanged; their contents remain forbidden.
- Runtime dependency direction and declarations are unchanged. The accepted test
  adds only standard-library imports and no runtime edge.
- Verification evidence: focused config 3/3, runtime environment 14/14,
  compileall, and diff-check pass. Full fallback has 49 outcomes: 38 pass, the
  baseline 10 dependency import errors, and the baseline 1 dependent failure;
  `sqlalchemy`, `aiosqlite`, and `playwright` remain unavailable.
- Goals: 5 `UNSATISFIED`, 4 `PARTIAL`, 2 `BLOCKED`. Cycle 0001 advanced
  `TD-007` and `TD-011`; both remain `PARTIAL`.
- Stale evidence: all Cycle 0001 optimization analysis and planning is stale for
  selecting another batch. Immutable baseline/target documents and refreshed
  coverage, dependency, ownership, and gate evidence remain valid.
- Authorized scope: reversible repository-local cleanup and hermetic tests that
  preserve behavior. No dependency installation, network, real DB/protected
  content, product/security decision, commit, push, deployment, or user-owned
  hunk change.
- Required wave: exactly three independent read-only A1-A3 analyses. Each must
  identify affected paths/callers, goals, invariant, dependencies, verification
  oracle, recovery class, risk, confidence, and blockers; the coordinator will
  select only the smallest coherent authorized batch.
