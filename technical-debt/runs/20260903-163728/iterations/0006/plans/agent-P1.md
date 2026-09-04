# Cycle 0006 P1 Change Plan

Verdict: `PROCEED` with an exact six-path allowlist. Add `service/repositories/__init__.py`, `service/repositories/accounts.py`, and `tests/test_account_repository_contract.py`; modify only `service/account_pool.py`, `service/services/account_service.py`, and `service/dependencies.py`.

The adapter dynamically delegates the ten account/candidate/proxy-read methods to `service_db`, preserves arguments/results/exceptions, and aliases the exact `AccountStatus` object. Pool, account service, and QR service receive trailing optional repository parameters. Dependencies constructs and injects one shared adapter. Existing Cycle 0005 account and architecture tests remain unchanged as compatibility oracles.

Tracked preimages: account pool `9D9ADBAE...67CB12` / `fc96bb7e...e35e96`; account service `3B95DD99...8D6DE` / `59375ecf...5c91c`; dependencies `274E7830...48CE2D` / `aacfff0b...eeedc`. New files have absent preimages. Recovery reverses exact hunks or removes only attributed new paths.
