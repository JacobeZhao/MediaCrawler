# Cycle 0001 Accepted Analysis

## Selected Batch

Advance `TD-007` and demonstrate `TD-011` by establishing a mechanical application-configuration contract.

Allowlist candidate: `.env.example`, `docs/config.md`, one new standard-library test module. Runtime `config/settings.py` and `.gitignore` are read-only evidence. No application default, parsing, behavior, dependency, secret, DB, network, version, user-owned file, or public contract may change.

Verified mismatch: `.env.example` omits eight active keys: `CRAWLER_TASK_START_JITTER_MIN_SEC`, `CRAWLER_TASK_START_JITTER_MAX_SEC`, `CRAWLER_ACCOUNT_REQUEST_BUDGET`, `CRAWLER_ACCOUNT_BUDGET_REST_MIN_SEC`, `CRAWLER_ACCOUNT_BUDGET_REST_MAX_SEC`, `CRAWLER_RISK_BACKOFF_SEC`, `CRAWLER_TASK_MAX_NOTES_PER_TASK`, `CRAWLER_TASK_MAX_COMMENTS_PER_NOTE`. `RUNTIME_LOCK_PATH` is documented but absent from the sample. `XHS_COOKIES` has no tracked runtime consumer.

Oracle: a deterministic standard-library test mechanically enumerates literal application environment inputs, checks sample/docs coverage, blank secret placeholders, intentional service-sample overrides, and exact runtime artifact exclusions including inclusion of tracked `cache/`. Focused test and `git diff --check` pass; broad fallback adds no failures beyond the baseline dependency errors.

Recovery: R1 exact Git preimages for tracked docs/sample; new test has a nonexistence preimage. Risk low, confidence high.

Rejected this cycle: every other candidate, because it has a separate invariant/oracle, needs unavailable dependencies, touches user-owned/protected state, or requires a product/security decision.
