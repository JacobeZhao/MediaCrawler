# Cycle 0008 P1 Change Plan

Verdict: `PASS`. Use a five-path allowlist: create `service/repositories/proxies.py` and `tests/test_proxy_repository_contract.py`; modify `service/services/proxy_service.py`, `service/dependencies.py`, and `tests/test_runtime_composition_contract.py`. Do not export through `service/repositories/__init__.py` because no current consumer uses that facade.

Implement five dynamic pass-through repository methods. Add a trailing optional repository to `ProxyService`, using an explicit `is not None` check, and route all persistence through it without changing behavior. Construct and inject one production repository. Keep the runtime contract at eight parents while adding the new constructor and identity. Add exactly five isolated proxy parents. Expected focused/broad totals are 82/82 and 114/103/10/1.

New files use absent-preimage R1 recovery. The three accepted dirty/untracked files require exact current-preimage R2 hunk recovery. Account lifecycle proxy lookup, service DB, routes, package facade, and existing tests remain read-only.
