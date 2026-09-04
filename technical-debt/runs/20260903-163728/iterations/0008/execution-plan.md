# Cycle 0008 Execution Plan

## Decision And Scope

Extract the proxy-management persistence boundary behind one injectable repository while preserving every existing service, HTTP, credential, diagnostic, and physical-database behavior.

P1-P3 all returned `PASS`. P2 proposed adding `ProxyRepository` to `service/repositories/__init__.py`; P1 and P3 found no facade consumer and the production composition imports concrete repository submodules. Omit that export to avoid enlarging the public surface.

E1 is the only code writer. Exact code allowlist:

- create `service/repositories/proxies.py`;
- create `tests/test_proxy_repository_contract.py` with exactly five parent tests;
- modify `service/services/proxy_service.py`;
- modify `service/dependencies.py`;
- modify only the construction-graph scenario/assertions in `tests/test_runtime_composition_contract.py`, retaining exactly eight parents.

All other paths are read-only, especially `service/service_db.py`, `service/repositories/__init__.py`, `service/repositories/accounts.py`, routes, schemas, account files, existing proxy/config/redaction/account tests, and four user-owned files.

## Recovery

Before writing, E1 must create and verify exact non-repository recovery preimages for these accepted run-owned paths:

| Path | Class | Current SHA-256 | Current Git blob |
| --- | --- | --- | --- |
| `service/services/proxy_service.py` | R2 | `BF5A174E5996319E2A8FC7AFEE9374808ED629B0B82BE7D6FD72EFD30B265251` | `6de63b7a0d5dfe1a59402dca9962e739077b2b02` |
| `service/dependencies.py` | R2 | `3BC1B98EE24EBAD0A005A8E4D509CA7778F851B208A36EB29C04E4C2909D2BF3` | `6762878c9587db90400df088c945f32e720d1685` |
| `tests/test_runtime_composition_contract.py` | R2 | `F1B38FCE0EFACC6791A7A4EF9811F38B0CB6143A2A5177735E63D920C38BB512` | `e076c0834fcc51913f194bac0665a39a095bc368` |

The two new paths are R1 absent preimages. Recovery runs in reverse checkpoint order, restores only Cycle 0008 hunks or the verified exact current preimages, removes new paths only when attribution/postimage matches, and never uses checkout/reset or changes the index.

## C1 Adapter And Contract

Create a stateless `ProxyRepository` with explicit async methods `list_proxy_profiles`, `get_proxy_profile`, `add_proxy_profile`, `update_proxy_profile`, and `delete_proxy_profile`. Each dynamically calls the same `service.service_db` facade function and returns or raises unchanged. Do not copy SQL or normalize data.

Create exactly five isolated standard-library parent tests:

1. all five adapter methods preserve dynamic lookup, args/kwargs, return identity, and exception identity;
2. default construction and explicit falsy repository injection preserve compatibility and identity;
3. list/create/update/delete preserve flags, ordering, normalization, dictionaries, and 400/404/409 matrices;
4. check preserves secret lookup, invalid/incomplete handling, synthetic HTTP URL/proxy/timeout, success/failure payload, fixed timestamp, redaction, returned full error, and persisted 500-character truncation;
5. static ownership and production composition preserve the account read, remove the service concrete edge, and construct/inject one shared proxy repository.

All dynamic cases run in bounded children with synthetic DB/HTTP/config/leaves, a minimal non-secret environment, temporary cwd/home/profile/temp/pycache/runtime, `-B`, `shell=False`, and one structured result. Any real DB/HTTP/proxy/browser/worker/default path is a failure.

Focused oracle: parent 1 proves C1 delegation before continuing.

## C2 Service Injection

Add `ProxyService(repository: ProxyRepository | None = None)` and preserve a supplied repository with an explicit `is not None` check. Replace only the five direct `sdb` calls. Preserve flags, ordering, exception causes/status/detail, response keys/messages, normalization, masking, datetime call, redaction, 500-character persisted truncation, HTTP URL/proxy/timeout, and zero-argument construction.

Focused oracle: new parents 2-4 plus unchanged proxy config 4/4 and diagnostic redaction 2/2.

## C3 Production Wiring

Construct exactly one `proxy_repository` in `service/dependencies.py` and pass it to `ProxyService`. Extend only the existing synthetic dependency graph with a proxy-repository stub/count and shared identity. Do not change accessors or lifecycle behavior.

Focused oracle: parent 5, new suite 5/5, runtime composition 8/8, and combined focused 82/82.

## Batch Gates

Run compileall, `git diff --check`, exact five-path Cycle 0008 scope, empty index, postimage/encoding/newline checks, static concrete-edge checks, and unchanged user-owned hashes. `python -B -m tools.verify` may return 1 only from the accepted broad fingerprint. Direct discovery must report exactly 114 outcomes: 103 pass, ten import errors, and one dependent failure caused only by missing `sqlalchemy`, `aiosqlite`, and `playwright`. E2 and E3 must both return final `PASS`.

Initial implementation plus at most two repairs are allowed. A third failed write-and-gate attempt triggers exact reverse recovery and `BLOCKED_TECHNICAL`. Any required schema, SQL, path, route, account ownership, credential representation, product/security behavior, install, network, real infrastructure, protected content, commit, push, or deployment is `BLOCK`.

Acceptance advances only the proxy-management slice of `TD-004` and strengthens `TD-002`, `TD-007`, and `TD-011`.
