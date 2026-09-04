# P1 Change Plan

Exact allowlist: create `tests/test_account_service_contract.py`,
`tests/test_account_pool_contract.py`, and
`tests/test_diagnostic_redaction_contract.py`; add one redaction import/expression
hunk in `service/services/proxy_service.py`; change only the QR post-login pong
error expression in `service/crawler_engine.py`. All other paths are read-only.

Use standard-library parent tests and bounded child interpreters with empty temp
env/pycache, explicit roots, failing DB/network/browser fakes, and one JSON result.
AccountService has six methods covering add, cookie, proxy, and QR success/failure
ordering and rollback currently explicit in source. AccountPool has six methods
covering ready selection, CAPTCHA/cooldown isolation, health recovery,
adopt/remove, startup failure, and public account projection. Diagnostics has
two final-invariant methods; pre-fix both fail only at final sentinel assertions,
then the exact two source corrections make them pass.

Projected new count: 14; focused total 64; broad result 96 outcomes, 85 passes,
10 accepted import errors, and 1 accepted dependent failure.
