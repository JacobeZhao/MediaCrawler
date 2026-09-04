# P3 Scope And Architecture Review

Verdict: `PASS` with mandatory cross-platform sequencing. One new test file is
sufficient; existing docs already state the contract.

Use readiness, released, and exit phases. The child acquires and signals ready,
then releases on command but remains alive. Only after release should the parent
read lock metadata and reacquire: Windows byte-range locking may prevent reading
byte 0 while held. Reacquiring while the child remains alive proves explicit
`release()`, not process exit, made the lock available. Then signal exit and
require a clean bounded child shutdown. Never use the default runtime path.

## Updated-Workflow Revision

Verdict: `REVISE`, not `SPLIT`. All four checkpoints are compatible. P3 adds
`docs/ai-change-guide.md` as a hidden consumer of the old primary command and
`tools/README.md` as owner of the new utility inventory. The verifier must be an
honest fixed-order orchestrator: current interpreter, repository cwd, no shell
or install, run all phases for diagnostics, and return nonzero if any phase
fails. Its real fallback run is expected to fail with the known dependency
fingerprint; no permissive missing-dependency option. Public-import, enforcement,
runtime, persistence, migration, and policy work stays excluded.
