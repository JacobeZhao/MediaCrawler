# Cycle 0005 Execution Plan

## Scope And Recovery

E1 is the only writer. Exact product allowlist:

- create `tests/test_account_service_contract.py`;
- create `tests/test_account_pool_contract.py`;
- create `tests/test_diagnostic_redaction_contract.py`;
- in `service/services/proxy_service.py`, add the existing canonical redaction
  import and sanitize only the caught proxy exception diagnostic;
- in `service/crawler_engine.py`, sanitize only the exception interpolation in
  the QR post-login pong failure response.

New tests are R1 absent-preimage checkpoints. Proxy preimage is SHA-256
`EAFB36C3E44CE5E695B997E0F289A287C858A974C25BFC502E721DC4C63EDB8A`,
blob `975911bb82547f13ad9390e31c4bdfa28937d711`. Crawler preimage is
`D656EC8350B6C6E16950134CB3CADF639AA0173461781DBAB058343B7893970F`,
blob `395c7197ab75116efd7fdde1af297568268af232`. Restore only exact task hunks and
remove only attributed new files; never reset/checkout or change the index.

Pin read-only account service/pool, redaction helper, schemas/routes/DB/manager,
accepted tests, HEAD, empty index, and all four user-owned hashes.

## Checkpoint 1: Account Service

Create six isolated parent methods with subcases:

1. add success validates/normalizes, persists, starts, marks active, then wakes;
   false startup deletes only the new row and returns current 400;
2. cookie success removes/restarts/persists active/wakes; false startup attempts
   restoration with exact old cookie/proxy, performs no DB mutation/wake, and
   returns current 400;
3. proxy `restart=False` validates and updates only proxy ID; restart success
   removes/starts/updates proxy then active;
4. proxy false restart attempts old-proxy restoration, performs no DB/status/
   wake mutation, and returns current 400;
5. verified QR orders session lookup/check, add, adopt same engine/account ID,
   active update, forget, wake, and returns the current cookie-free response;
6. pending/error and done-unverified QR preserve current pending/400 behavior
   without persistence/adoption/forget/wake.

Do not assert rollback for raised pool/status/wake errors, failed restoration, or
post-insert QR failures where source defines none. Focused oracle: 6/6.

## Checkpoint 2: Account Pool

Create six isolated methods using fake engines, IDs, monotonic clock, explicit
temporary project root, guarded paths, and deterministic barriers:

1. ready selection/controlled rotation skips CAPTCHA/cooling and uses ready
   default only as fallback;
2. concurrent CAPTCHA and cooldown operations update only their exact accounts;
3. deadline expiry remains cooling pending health; successful probe alone makes
   ready/active and resets failure state;
4. adopt/remove preserves identities and stops only the removed engine;
5. start exception/invalid cookie stops and never registers the engine, while
   missing/inactive proxy short-circuits before construction;
6. public account projection preserves exact keys, runtime precedence, masked
   proxy, and cookie preview without raw credential values.

No background loops, wall-clock sleeps, real profile/browser/DB/network, or
unevidenced fairness/atomicity assertion. Focused oracle: 6/6.

## Checkpoint 3: Atomic Diagnostic Red/Green

Create two final-invariant child-isolated tests. Before source edits, run a
private leak mode that emits booleans only and prove precisely two sentinel
assertions fail after all state/call assertions pass.

Proxy failure preserves exact response keys, false state/message, exception
class prefix, one timestamped DB update, and the existing 500-character stored
cap; returned and persisted diagnostics contain no synthetic URL-userinfo,
password, token, Authorization, or Cookie sentinel. Keep success unchanged.

QR pong failure preserves `done=True`, `verified=False`, exact legacy cookie,
prefix, flow, and status; only returned diagnostic and existing log must omit
the separate exception sentinel. Keep verified success unchanged.

Apply exactly:

- `error = f"{type(exc).__name__}: {redact_sensitive_text(exc)}"` in proxy
  handling, plus its import;
- `f"post-login verification failed: {redact_sensitive_text(exc)}"` in the QR
  error value.

Then require diagnostic 2/2 and rerun account checkpoints.

## Batch Gates

All parents use `sys.executable -B -c`, `shell=False`, repository cwd/PYTHONPATH,
dedicated temporary empty env/pycache/root, minimal environment, captured text,
10-second timeout, and child-only stubs. Target methods and
`tools.redaction.redact_sensitive_text` remain real.

Expected new tests: 14/14; total focused: 64/64. `python -B -m tools.verify`
and direct discovery must produce 96 outcomes, 85 passes, the same 10 import
errors and 1 dependent failure caused only by missing `sqlalchemy`, `aiosqlite`,
and `playwright`. Also require compileall, diff/encoding/whitespace, exact
five-path scope, empty index, all hashes, module isolation, and protected/default
runtime metadata checks.

No other response, cookie, log policy, persistence, runtime-container, resource,
dependency, migration, security/deployment decision, user file, external action,
commit, push, or deployment is authorized.
