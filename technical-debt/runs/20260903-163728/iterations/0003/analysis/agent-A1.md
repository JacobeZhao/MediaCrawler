# A1 Gap And Structure

Manifest parity is complete, but the environment/lock/unified gate remain for
`TD-001`. Composition and persistence work remains dependency-blocked and
under-characterized; no move or deletion is justified.

Ranked ready candidates: (1) new cross-process runtime-lock characterization for
`TD-002`/`TD-011` and as a `TD-003` prerequisite; (2) new image downloader
characterization for `TD-002`/`TD-008`; (3) pure proxy characterization. Public
imports and composition/persistence/attribution/migration work are deferred.

A1 recommends only `tests/test_runtime_lock.py`: explicit temporary lock path,
bounded child readiness/release handshake, contention failure without holder PID
replacement, clean release, reacquisition, and idempotent release. The user-owned
implementation stays hash-pinned and read-only. R1 nonexistence recovery;
low-medium risk, high confidence.
