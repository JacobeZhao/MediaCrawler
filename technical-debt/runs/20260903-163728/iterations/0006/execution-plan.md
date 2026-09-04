# Cycle 0006 Execution Plan

## Scope, Writer, And Recovery

E1 is the only repository writer. Exact six-path allowlist:

- create `service/repositories/__init__.py`;
- create `service/repositories/accounts.py`;
- modify `service/account_pool.py`;
- modify `service/services/account_service.py`;
- modify `service/dependencies.py`;
- create `tests/test_account_repository_contract.py` with exactly five parent tests.

All other paths are read-only, including existing account/architecture tests, `service/service_db.py`, main/app/routes/executors/task manager, crawler/proxy code, databases, runtime paths, and four user-owned files.

Tracked R1 preimages:

| Path | SHA-256 | Git blob |
| --- | --- | --- |
| `service/account_pool.py` | `9D9ADBAE60DFF10DFDC58D2D22DDD23909D48CB154E1D806C9F5ECA2E767CB12` | `fc96bb7e6a7b7cc974a0e5202603a47fc8e35e96` |
| `service/services/account_service.py` | `3B95DD9935A40D6D8459DE7BDD48D1816FF54D498808E0A8057936684038D6DE` | `59375ecf418fc005116c8fbf7e1447d69e65c91c` |
| `service/dependencies.py` | `274E783083A2F60C0816F2A26E215433973FAA8419611770AD9D97C3A548CE2D` | `aacfff0b268de1f8ea8795e03ec23eaa385eeedc` |

New paths have R1 absent preimages. Recover only exact task hunks and attributed new paths; never checkout/reset or alter the index. Pool and account-service injection are one coherent recovery checkpoint.

## Checkpoint 1: Account Repository Adapter And Contract

Create a stateless adapter that dynamically looks up `service.service_db` on every call. Export exactly `AccountRepository` and the exact `AccountStatus` alias. Provide explicit async pass-through methods for `get_active_accounts`, `update_account`, `get_account`, `get_proxy_profile`, `list_accounts`, `add_account`, `delete_account`, `list_candidate_accounts`, `upsert_candidate_account`, and `delete_candidate_account`. Do not normalize, copy, catch, wrap, or extend operations.

The first repository-contract parent test proves exact enum identity, all delegation args/kwargs/results, and exception identity using a child fake. No real database import or call is permitted.

## Checkpoint 2: Inject The Account Ownership Boundary

AccountPool removes its concrete DB import, accepts an optional second repository argument, defaults with an explicit `is not None` check, and routes every account/proxy operation and status enum through the adapter. Preserve path, timing, lock, loop, status, identity, and call order.

AccountService and QrSessionService remove the concrete DB import and add only trailing optional repository parameters while preserving current positional signatures. `_get_active_proxy_or_error` retains its current call compatibility and accepts an optional repository; instance calls pass their injected adapter. Route all account/candidate/proxy reads and writes through it without changing HTTP details, response dictionaries, cookie behavior, QR ownership, rollback, wakeups, or ordering.

Four additional repository-contract parent tests prove pool injection, service/QR injection, candidate operations, static concrete-edge removal, default constructors, and no unexpected concrete DB call. The unchanged Cycle 0005 account suites must remain 12/12.

## Checkpoint 3: Shared Production Wiring

Dependencies imports and constructs exactly one `AccountRepository`, then passes that identical object to pool, QR service, and account service. Keep all existing globals/accessors and other construction/import-time behavior unchanged. Isolated fake-constructor evidence must prove shared identity without instantiating real clients, DBs, browsers, queues, or workers.

## Gates

- New repository contract: 5/5.
- Existing account suites plus new contract: 17/17.
- Previously accepted focused 64 plus new contract: 69/69.
- Expected direct broad result: 101 outcomes, 90 pass, unchanged 10 import errors and 1 dependent failure caused only by `sqlalchemy`, `aiosqlite`, and `playwright`.
- `python -B -m tools.verify`, direct discovery, compileall, `git diff --check`, exact six-path scope, static dependency ownership, empty index, pre/postimage hashes, user-owned hashes, encoding/newline/whitespace, module isolation, and default/protected runtime metadata checks.

Stop or split if `service_db` must change, a copied enum or broader repository API is needed, constructor compatibility fails, another production caller must change, or any oracle requires real infrastructure. This batch advances only the account slice of `TD-004` to `PARTIAL`; it does not resolve runtime composition, content persistence, resource/security policy, migrations, or external compatibility.
