# Cycle 0006 A3 Minimality And Sequencing

A3 recommends extracting the account lifecycle persistence boundary behind an injected repository adapter. Cycle 0005 now makes account service/pool orchestration, identity, cooldown, projection, and recovery observable. The adapter would preserve `service_db` as the schema/compatibility facade while removing direct account persistence imports from `AccountService`, `QrSessionService`, and `AccountPool`.

The proposed batch adds `service/repositories/` and an isolated adapter contract; it preserves constructor compatibility, `service_db.AccountStatus` identity, exact delegation, response shapes, and one shared adapter in `dependencies.py`. It advances `TD-004` only to `PARTIAL`. Risk: medium-low; confidence: 0.84. No repository write or protected/external access occurred.
