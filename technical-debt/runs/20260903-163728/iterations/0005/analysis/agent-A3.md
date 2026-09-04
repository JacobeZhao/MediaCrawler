# A3 Minimality And Sequencing

Read-only fresh analysis; no files changed.

A3 identified the last justified characterization-first batch: new isolated
contracts for `AccountService` and `AccountPool`. Required behavior includes
add/start rollback, cookie and proxy replacement recovery, QR ownership
transfer, paused-task wakeup, ready rotation, CAPTCHA/cooldown isolation,
adopt/remove identity, concurrency separation, and startup-failure cleanup.

Both tests must use bounded child/module isolation, temporary roots, fake clocks
and engines, and AsyncMock DB/pool/session/manager collaborators. They have R1
nonexistence preimages and provide prerequisites for `TD-003/004` without real
DB/browser/network access. A3 rejected direct runtime/persistence extraction in
the current dependency-limited environment and rejected further static
inventory work that would not change readiness.
