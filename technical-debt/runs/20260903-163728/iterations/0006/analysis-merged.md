# Cycle 0006 Analysis Merge

## Evidence And Dissent

All three analysts used the refreshed 143/143 tree and accepted 96/85/10/1 baseline. A1 and A2 agree `TD-003` still lacks import/lifespan/accessor characterization. A1 would combine that evidence with a production composition rewrite; A2 rejects the rewrite until the characterization is independently accepted. A3 instead identifies an account repository boundary unlocked by Cycle 0005 contracts.

The coordinator rejects a production composition rewrite this cycle: pre-lifespan accessor semantics and failure cleanup are not yet evidenced, and changing them together with their first oracle would be too risky. The test-only composition contract remains ready but does not complete a structural boundary.

## Selected Candidate

Advance the account lifecycle portion of `TD-004` behind a narrow injected repository adapter, subject to planning proving all of the following:

- no operational SQL, schema, path, or `service_db` public function changes;
- exact dynamic delegation of arguments, keyword arguments, return values, and `AccountStatus` identity;
- default-compatible existing constructors and one shared adapter at the production composition point;
- account service/pool no longer import concrete `service_db` directly;
- Cycle 0005 behavior tests remain valid and injected-fake tests prove no concrete DB edge is used;
- no real database, browser, network, proxy, background loop, protected content, or missing-package installation is required.

The likely allowlist is `service/repositories/__init__.py`, `service/repositories/accounts.py`, `service/services/account_service.py`, `service/account_pool.py`, `service/dependencies.py`, the two Cycle 0005 account contracts, `tests/test_architecture_contract.py`, and one new repository contract. Planning must minimize this list and may return `SPLIT` or select the test-only composition contract if delegation, enum identity, or hidden constructor compatibility cannot be proven hermetically.

Goals: primary `TD-004`; supporting `TD-002`, `TD-006`, and `TD-011`. `TD-004` may become only `PARTIAL`. `TD-003`, `TD-005`, `TD-008`, and blocked `TD-009/010` are deferred.
