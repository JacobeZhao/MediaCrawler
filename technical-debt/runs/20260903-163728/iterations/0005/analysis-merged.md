# Cycle 0005 Analysis Merge

## Evidence Decision

The explicit runtime-composition gap is accepted but not selected. A1's central
refactor changes all route accessors and lifecycle ownership while the actual
dependency-backed app/lifespan suites cannot collect. A2 and A3 independently
require more account/lifecycle characterization first. Sentinel-only imports do
not adequately prove browser, persistence, and cleanup compatibility for that
production rewrite.

A2's diagnostic findings are ready and are not new policy. The repository's
existing redaction helper and documented diagnostic invariant establish intended
behavior. Current proxy and QR exception paths demonstrably bypass that helper
for returned or persisted error text. A narrow correction may therefore proceed
without deciding authentication, CORS, listener trust, cookie projection,
encryption, destination policy, or release version.

## Accepted Largest Compatible Batch

Select four ordered checkpoints in one account-state/diagnostic-safety batch:

1. New `tests/test_account_service_contract.py` characterizes account add,
   cookie/proxy replacement, QR transfer, rollback, ordering, and paused-task
   wake behavior using isolated fake collaborators.
2. New `tests/test_account_pool_contract.py` characterizes per-account ready
   selection/rotation, CAPTCHA/cooldown isolation, adopt/remove identity,
   concurrent separation, and startup-failure cleanup.
3. New `tests/test_diagnostic_redaction_contract.py` first reproduces proxy and
   QR sentinel leaks in bounded dependency-isolated children without real
   external actions.
4. Narrowly modify `service/services/proxy_service.py` and
   `service/crawler_engine.py` to route only those raw exception diagnostics
   through `tools.redaction.redact_sensitive_text`, preserving response keys,
   status, persistence calls, success behavior, and legacy cookie projection.

Goals: advance `TD-002` and `TD-011`, add prerequisite evidence for
`TD-003/004`, strengthen the provider/account boundary in `TD-006`, and repair
a bounded documented invariant adjacent to blocked `TD-010` without changing
its `BLOCKED` status.

The checkpoints share account/proxy/browser failure ownership, R1 exact or
nonexistence recovery, dependency-isolated hermetic oracles, and no product
decision. Each remains independently recoverable. Planning must split or reject
any case that requires real DB/browser/profile/network access, a default runtime
path, changes to response fields/cookies, or source edits beyond the two exact
diagnostic expressions.

## Gates

Plans must pin all source/user preimages, prove module/subprocess cleanup, and
define exact call-order/state oracles rather than implementation-shaped mocks.
Run each focused checkpoint, existing focused 50/50, `python -B -m tools.verify`,
direct discovery, compile/diff/encoding/scope/index/hash checks. For `N` new
methods, broad outcomes and passes must be exactly `82 + N` and `71 + N`, with
the same 10 import errors and 1 dependent failure caused only by unavailable
`sqlalchemy`, `aiosqlite`, and `playwright`.

No runtime-container/persistence extraction, dependency install/lock, migration,
resource threshold, security/deployment decision, real external action,
protected-content access, commit, push, or deployment is permitted.
