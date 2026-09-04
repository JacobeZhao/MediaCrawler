# Cycle 0008 Input

## Live Baseline

- Cycle 0007 accepted; branch `dev`, HEAD `f7f99aeff476c3cbe2959cbc69130a02918c57ce`, index empty.
- Coverage: 147/147 project paths, comprising 130 baseline tracked paths and seventeen accepted new source/test/tool paths.
- Goals: 2 `UNSATISFIED`, 7 `PARTIAL`, 2 `BLOCKED`.
- Runtime composition now has an isolated eight-test migration contract; production still constructs singletons and projects compatibility config at import.

## Gates And Boundaries

- Combined focused suite: 77/77.
- Broad discovery: 109 outcomes, 98 pass, 10 import errors, 1 dependent failure; missing modules remain only `sqlalchemy`, `aiosqlite`, and `playwright`.
- User-owned and protected boundaries are unchanged. No installation, network, real infrastructure, migration, product/security/deployment decision, commit, push, or deployment is authorized.
- Cycle 0007 used its third and final attempt before acceptance. New Cycle 0008 candidates require fresh recovery and gate budgets.

## Wave A Assignment

Freshly compare every `UNSATISFIED` and `PARTIAL` goal with the live tree. Reassess the now-characterized explicit runtime-container migration and the deferred proxy repository extraction as distinct production candidates. Identify the largest coherent authorized batch with exact paths, callers, invariants, hermetic oracles, dependencies, recovery class, risk, confidence, and product boundaries. Do not reuse Cycle 0007 rankings and do not write.
