# Cycle 0008 Analysis Merge

## Decision

Select only the injectable proxy management repository boundary for planning. All three analysts identify it as ready, hermetic, reversible, and free of product or schema decisions. A1 proposed combining it with runtime composition; A3 preferred runtime composition first; A2 preferred proxy alone. The coordinator rejects runtime work in this cycle because the evidence does not decide accessor behavior outside an active lifespan, compatibility of legacy module-level singleton names, partial graph-construction cleanup, or build/lock ordering. Choosing those semantics would exceed cleanup authority.

Runtime composition remains a high-value candidate but is deferred, not rejected. Its Cycle 0007 contract remains valid current-state evidence.

## Selected Batch

Expected exact code scope for planning:

- create `service/repositories/proxies.py`;
- create `tests/test_proxy_repository_contract.py` with a fixed count to be resolved by planning;
- modify `service/services/proxy_service.py` for optional repository injection;
- modify `service/dependencies.py` to construct and inject one shared proxy repository;
- modify `tests/test_runtime_composition_contract.py` only as necessary to preserve the production construction-graph oracle;
- planning must decide whether `service/repositories/__init__.py` needs an export; omit it unless an established package-facade convention requires it.

The adapter dynamically delegates the five existing proxy-profile facade operations. Preserve all SQL/schema/path/transaction behavior, arguments, return dictionaries, exceptions, secret flags, timestamps, normalization, diagnostic redaction/truncation, HTTP payloads, route/accessor contracts, and account-lifecycle proxy lookup. `service/service_db.py`, routes, account repository/pool/service, existing proxy and redaction tests, and user-owned paths remain read-only.

Planning must define exact R1/R2 current preimages for accepted dirty/untracked paths, a fixed parent-test count, focused/broad totals, default-constructor compatibility, static concrete-edge rejection, shared production identity, fake DB/HTTP isolation, and independent recovery checkpoints. No real DB, proxy, HTTP, browser, worker, default runtime path, protected content, install, network, migration, product decision, commit, push, or deployment is allowed.

Expected target effect: advance the proxy-management slice of `TD-004` and strengthen `TD-002`, `TD-007`, and `TD-011`; do not claim operational persistence complete.
