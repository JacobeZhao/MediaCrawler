# P1 Change Plan

Create only `tests/test_runtime_lock.py`; pin the user-owned implementation hash.
P1 proposes one end-to-end standard-library test using a long-lived child that
acquires an explicit temporary path, writes a separate readiness marker, waits
for a release command, and exits cleanly. The parent verifies contention and
the exact public error, unchanged holder metadata, child release, parent
reacquisition, parent PID write, and idempotent release. All waits and cleanup
are bounded; child environment uses the repository path, empty env selector,
and suppressed bytecode. R1 recovery is test nonexistence.

## Updated-Workflow Revision

Expand to four independently recoverable checkpoints: retain runtime-lock;
create five image-downloader tests; create four proxy-config tests; create
`tools/verify.py` with four mocked contract tests and narrow updates to
`docs/testing.md` and `docs/ai-change-guide.md`. P1's exact expanded allowlist
has seven paths. Each checkpoint has its own focused gate; broad fallback is
projected as 55 passes, 10 import errors, and 1 dependent failure across 66
outcomes. No production source or dependency value changes.
