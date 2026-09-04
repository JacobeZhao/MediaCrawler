# Cycle 0007 P3 Scope And Architecture Review

- Verdict: `PASS`.
- The single-file test batch is the smallest complete prerequisite for `TD-003`; proxy repository extraction has a different production, recovery, and verification boundary and remains deferred.
- Exact code scope is only `tests/test_runtime_composition_contract.py`; all production, existing test, config, dependency, documentation, route, service, repository, and static paths are excluded.
- Proposed parent count: seven by grouping related application and lifecycle cases.
- Guardrails: assert identities and public behavior, not source text, line numbers, reprs, random IDs, FastAPI auto-routes, or private Starlette representation.
- Current import-time construction/config mutation/app creation/image-directory event, cleanup of not-started objects, and cleanup-error precedence are migration evidence rather than endorsed target invariants.
- Known callers include `start_xhs_service.py`, the `service.app:app` facade, seven route modules using eight accessors, `test_architecture_contract.py`, and the dependency-bound existing lifespan tests.
- Acceptance requires isolated new tests, unchanged baseline failure fingerprint, exact scope and hashes, and independent E2/E3 `PASS`; `TD-003` remains `UNSATISFIED` with its prerequisite evidence strengthened.
