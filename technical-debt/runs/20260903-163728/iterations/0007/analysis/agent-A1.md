# Cycle 0007 A1 Gap And Structure

A1 recommends one test-only runtime composition/lifespan contract. Current imports construct the graph and mutate compatibility config; app creation registers routes/mounts and creates the image directory. Existing lifecycle tests cover only three cleanup cases and cannot collect without SQLAlchemy. The new isolated contract should cover graph/accessor identity, app shape, enabled/disabled startup order, normal shutdown, pre-yield failures, cleanup continuation, and first-error behavior without endorsing import-time construction as the target.

Write scope: only `tests/test_runtime_composition_contract.py`, R1 absent preimage. Primary progress: `TD-002`, prerequisite for `TD-003`, supporting `TD-007/011`. Risk low-medium; confidence 0.91. Proxy/task/content/resource work is deferred.
