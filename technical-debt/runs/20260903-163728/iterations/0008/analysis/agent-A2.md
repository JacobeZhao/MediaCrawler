# Cycle 0008 A2 Behavior And Risk

A2 recommended only the proxy repository boundary. Runtime container work still lacks evidence-backed semantics for accessors outside lifespan, old module-level singleton consumers, partial construction cleanup, repeated/concurrent lifespan, and lock-versus-build order. Combining it with proxy persistence would mix risk and recovery boundaries.

The ready proxy batch creates `service/repositories/proxies.py` and `tests/test_proxy_repository_contract.py`, then injects the adapter through `service/services/proxy_service.py` and `service/dependencies.py` while updating the runtime composition contract. SQL, schema, path, routes, payloads, secret flags, normalization, diagnostics, and HTTP behavior remain unchanged. Proposed five new parent tests; confidence `0.94`.

Verdict: `PASS_TO_PLANNING` for proxy only; defer runtime container.
