# Cycle 0001 Execution Plan

## Invariant And Goals

Advance `TD-007` and `TD-011`: application configuration sample/docs must mechanically match literal `Settings` environment inputs without changing runtime behavior.

## Writer And Allowlist

E1 is the only writer during implementation. Exact product allowlist:

- `.env.example`: add commented `RUNTIME_LOCK_PATH` and eight missing crawler keys with existing defaults; retain blank `XHS_COOKIES` and all existing service-oriented values.
- `docs/config.md`: state `.env.example` is exhaustive; document service-mode overrides, reserved compatibility input, selector and supervisor ownership, sensitive blanks, and grouped control semantics without duplicating every name.
- `tests/test_config_contract.py`: new standard-library AST/text/Git contract tests.

Read-only evidence: `config/settings.py`, `.gitignore`. Everything else is forbidden.

## Test Contract

AST-enumerate literal environment reads within `Settings`, including multiline calls. Sample must contain every active name; only blank `XHS_COOKIES` may be sample-only. Active defaults match, except `HEADLESS=true`, `CDP_CONNECT_EXISTING=false`, and constructed path examples. `JUSTONEAPI_TOKEN`/`XHS_COOKIES` remain blank. Docs preserve precedence and delegate inventory. Bounded `git check-ignore`/`git ls-files` checks classify representative artifacts without opening them and prove tracked `cache/local_cache.py` remains source.

## Recovery

R1 blobs: `.env.example` `efb74870ce3eb0a48556f218fe21bf93b3442d7f`; `docs/config.md` `1877eae8eeed6e085a5a996d040c01f38970e936`; test nonexistence. Restore only accepted task hunks/new file, never index/reset/checkout.

## Gates

1. Focused: `python -m unittest discover -s tests -p test_config_contract.py -v`.
2. `git diff --check -- .env.example docs/config.md tests/test_config_contract.py`.
3. Compile with bytecode redirected outside repository.
4. Full fallback discovery; only exact established missing-dependency failures may remain.
5. Diff limited to allowlist plus run docs, no staged paths, and exact user-owned hashes unchanged.

E2 and E3 inspect only after E1 completes its coherent write and focused checks. Both must return PASS.
