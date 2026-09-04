# Cycle 0007 Analysis Merge

## Decision

Select one test-only runtime composition and lifespan characterization file. A1 and A3 independently rank this as the highest-confidence prerequisite for `TD-003`. A2's proxy repository slice is ready in isolation, but it has a distinct production/recovery boundary and ambiguous overlap with account lifecycle proxy reads, so it is deferred rather than combined.

## Selected Batch

Create only `tests/test_runtime_composition_contract.py`. Production and existing tests remain read-only. The contract must use bounded isolated children with synthetic modules and temporary environment/root/pycache to prove:

- exact current construction graph, shared identities, and accessor identities;
- `service.app:app`, router order, mounts, root branch, middleware, title/version, and lifespan association;
- exact enabled and disabled startup order;
- normal teardown and cleanup continuation/first-error behavior, including representative pre-yield failures;
- current known config projection and import/app filesystem events without treating import-time side effects as the desired target;
- no real DB, browser, HTTP, proxy, queue worker, background task, protected path, or default runtime path is accessed.

Planning must keep assertions behavioral rather than coupled to incidental implementation text, choose a fixed parent-test count, define fake-module boundaries and failure matrix, and ensure later `TD-003` can deliberately update the characterization to its target oracle. R1 recovery is removal of the attributed new file only.

Expected goals: `TD-002`, `TD-007`, and `TD-011` gain evidence; `TD-003` remains `UNSATISFIED` but becomes ready for a separately planned structural batch. Proxy repository extraction remains the next production candidate. All other deferred and blocked boundaries remain unchanged.
