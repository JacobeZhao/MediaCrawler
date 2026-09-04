# P2 Verification And Recovery Plan

Writable allowlist is new `tests/test_runtime_lock.py` only. Its preimage is
nonexistence; `service/runtime_lock.py` is read-only at SHA-256
`3894DF26CA11DE868A25B7DC8F99AD8AB30A693AFFB3DA9E73EAF582E606BF64`.

Use standard-library subprocess/tempfile primitives, explicit paths, exact
error/PID/reacquisition/idempotence assertions, `sys.executable`, repository
`PYTHONPATH`, bounded 10-second waits, no sleeps as synchronization, and
`finally` release/kill/wait cleanup. Run focused runtime-lock, existing
dependency/config/runtime-env, compile/whitespace, scope/hash/index, and broad
gates. If one test is added, broad must be 42/10/1. Any hang, PID replacement,
cleanup failure, scope drift, or new regression rejects the attempt. Recover
only the attributed new file; after three failures mark `BLOCKED_TECHNICAL`.

## Updated-Workflow Revision

Verdict: `REVISE` before continued execution. Keep the combined cycle, but make
the retained runtime-lock test use one monotonic 10-second wall-clock deadline
across spawn, handshakes, exit, and forced cleanup. Add image, proxy, and unified
verifier checkpoints with independent R1 rollback. P2's verifier scope includes
`tools/verify.py`, `tests/test_verify.py`, and one attributable
`docs/testing.md` hunk. All network/filesystem subprocess behavior is mocked or
OS-temporary; broad acceptance uses `42 + I + P + V` passes with the exact
10-error/1-failure dependency fingerprint.
