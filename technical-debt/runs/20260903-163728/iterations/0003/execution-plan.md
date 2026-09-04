# Cycle 0003 Execution Plan

## Scope And Invariant

Advance `TD-002` and `TD-011` and provide `TD-003` prerequisite evidence by
characterizing real cross-process runtime locking without editing production or
user-owned source.

E1 is the only writer. Exact product allowlist: new
`tests/test_runtime_lock.py`. Read-only `service/runtime_lock.py` must retain
SHA-256
`3894DF26CA11DE868A25B7DC8F99AD8AB30A693AFFB3DA9E73EAF582E606BF64`.
All other product paths are forbidden.

## Required Test

One standard-library end-to-end test uses an explicit nested path under
`TemporaryDirectory`. Spawn `sys.executable -B -c` without a shell, with
repository cwd/PYTHONPATH, empty `XHS_ENV_FILE`, suppressed bytecode, text pipes,
and bounded waits.

The child acquires, atomically signals readiness with its PID, waits for
`release`, releases, signals released, stays alive until `exit`, and always
releases in `finally`. The parent verifies readiness/child liveness; a separate
contender raises the exact documented `RuntimeError` and releases harmlessly.
After the child signals release, verify its PID remains in the lock file, then
reacquire while the child is alive, verify parent PID, and release twice. Finally
signal exit and require code 0. Cleanup attempts protocol completion, then
bounded kill/wait as last resort.

Do not read lock-file byte 0 while held: Windows may deny it. No default runtime
path, network, DB, protected content, dependency, docs, implementation, user
hunk, commit, push, or deployment action.

## Recovery And Gates

R1 nonexistence preimage. Recover only the new file after confirming ownership;
never reset/checkout/index-change.

Focused runtime-lock must pass 1/1. Existing dependency/config/runtime-env gates,
compileall, new-file UTF-8/newline/trailing-space check, exact scope/index/hashes,
and broad discovery must pass proportionally. Expected broad result: 53 outcomes,
42 pass, unchanged 10 import errors and 1 dependent failure with only the known
missing-package fingerprint.

## Updated-Workflow Superseding Plan

The preceding single-checkpoint plan is superseded by the updated workflow's
largest-compatible-batch rule. E1 remains the sole writer.

### Exact Allowlist

- Retain and repair `tests/test_runtime_lock.py` only for one shared 10-second
  wall-clock deadline.
- Create `tests/test_image_downloader.py`.
- Create `tests/test_proxy_config.py`.
- Create `tools/verify.py`.
- Create `tests/test_verification.py`.
- Modify only verification-command sections in `docs/testing.md` and
  `docs/ai-change-guide.md`.
- Add only the `tools.verify` inventory entry to `tools/README.md`.

Production evidence `service/runtime_lock.py`, `service/image_downloader.py`,
and `service/proxy_config.py` is read-only at the hashes recorded by P2/P3.

### Ordered Checkpoints

1. Runtime lock: preserve its R1 absent preimage/current completed checkpoint;
   repair only the global deadline, then pass 1/1.
2. Image downloader: standard-library fakes/temp directories characterize URL
   extraction/normalization, cache reuse, headers/timeout, content-type extension,
   exact bytes, atomic replace/temp cleanup including failure, limit/order, and
   per-item failure isolation. Do not freeze multi-extension set order or add
   future resource/destination policy.
3. Proxy config: pure table-driven tests characterize blank/bare/supported
   servers, current validation errors, credential quoting, Playwright mapping,
   password-without-username, and masking/redaction without network or caller
   imports.
4. Verification entry: `python -m tools.verify` uses standard library,
   `sys.executable -B`, fixed repository cwd, isolated environment/temp bytecode,
   and no shell/install/network. Run labeled dependency/config contract phases,
   compileall, then full discovery; continue all phases for diagnostics and
   return nonzero if any failed. Mocked tests prove exact commands/order/cwd/env,
   no import-time execution, all-phase execution, and status propagation. Docs
   make this primary for a provisioned environment, explicitly say it does not
   install/resolve, and retain focused diagnostics.

Each checkpoint has R1 nonexistence or exact-hunk recovery and may be rolled back
without discarding earlier accepted checkpoints. `docs/testing.md` recovery uses
its current pre-checkpoint bytes, not HEAD, preserving Cycle 0002.

### Gates And Boundaries

Run each new focused suite, existing config/dependency/runtime-env suites,
compileall, UTF-8/newline/whitespace checks, exact diff/index/hash checks, then
the real verifier and direct broad discovery. The verifier must honestly return
nonzero in the current missing-dependency environment with exactly the existing
10 import errors and 1 dependent failure. Record the exact new method count;
projected 14 methods yield 66 outcomes and 55 passes.

No production/user-owned edits, resource enforcement, public-import decisions,
runtime composition, persistence, attribution, migrations, lock generation,
dependency changes/install, network, real DB/proxy/browser, protected content,
product/security decisions, commit, push, or deployment.
