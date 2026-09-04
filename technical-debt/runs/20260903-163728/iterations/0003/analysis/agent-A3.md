# A3 Minimality And Sequencing

A3 ranks runtime-lock characterization first, image downloader characterization
second, and a narrow public-import smoke manifest third. Composition,
persistence, attribution, locking/resolution, migrations, policy changes, and
structural movement are deferred or blocked.

Recommended batch: create only `tests/test_runtime_lock.py`. A bounded child
process acquires an explicit temporary path and signals readiness; the parent
verifies contention raises the documented error without replacing the holder
PID, releases the child, reacquires, verifies its own PID, and releases twice.
No default runtime path or implementation edit. R1 nonexistence recovery, low
risk, high confidence. This advances `TD-002`, prepares `TD-003`, and exercises
`TD-011` without satisfying them.
