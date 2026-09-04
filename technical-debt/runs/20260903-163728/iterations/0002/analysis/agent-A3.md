# A3 Minimality And Sequencing

## Challenge

Composition and persistence goals remain unverifiable with SQLAlchemy,
aiosqlite, and Playwright unavailable. Lock generation, real migrations,
security/release policy, and destination policy require authority or external
evidence. The next batch should therefore be one dependency-free prerequisite
test without runtime changes.

## Ranked Candidates

1. `TD-002`/`TD-011`: cross-process runtime-lock characterization in new
   `tests/test_runtime_lock.py` only. Use an explicit temporary path, bounded
   child-process handshake, contention, unchanged owner PID, reacquisition, and
   idempotent release checks. R1, low-medium risk, high confidence.
2. `TD-002`/`TD-008`: characterize image downloader behavior with mocked URL
   responses and a temporary directory. R1, low risk, high confidence.
3. `TD-007`: a public import contract, limited by unknown external consumers.
4. Defer bounded fetch implementation, runtime composition, persistence,
   attribution, migration, and policy work.

## Recommendation

Select only cross-process runtime-lock characterization. Do not instantiate the
default runtime path or edit the user-owned `service/runtime_lock.py`.
