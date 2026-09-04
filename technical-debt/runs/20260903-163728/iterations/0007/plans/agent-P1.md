# Cycle 0007 P1 Change Plan

- Verdict: `PASS`.
- Exact code allowlist: create only `tests/test_runtime_composition_contract.py`; production files and existing tests remain read-only.
- Proposed parent count: nine. Separate dependency graph, config/import events, app export/shape, root/static branches, enabled and disabled lifecycle, startup failures, and cleanup failures.
- Construction oracle: real `service.dependencies` with synthetic leaf modules constructs each singleton once, preserves shared repository/engine/pool/client/registry/manager identities, and all eight accessors return their module instances.
- Application oracle: `service.app:app` is created once; title, version, lifespan, CORS, router order, mounts, and both root-response branches remain compatible.
- Lifecycle oracle: exact enabled/disabled startup order, full normal teardown, pre-yield failure boundary, cleanup continuation, and first-cleanup-error propagation are observable.
- Isolation: one bounded child per parent test, temporary cwd/environment/root/pycache, synthetic infrastructure, one JSON result, no real DB/browser/network/proxy/worker/default runtime path.
- Recovery: `R1`, absent preimage; remove only the attributed new file.
- Stop if production edits, real dependencies, protected content, or implementation-text assertions become necessary.

The import-time construction, compatibility projection, directory creation, and cleanup precedence assertions characterize current behavior only. They are expected to change in the later `TD-003` container migration.
