# P2 Verification And Recovery Plan

## Preimages

- `requirements.txt`: clean tracked blob
  `1df7c9713034c6ba95ce131dc7404c7aa3a44fc3`.
- `docs/testing.md`: clean tracked blob
  `1fdc75086bbc64374ae6d482cb12eb28e41d923f`.
- `tests/test_dependency_contract.py`: absent from HEAD, index, and worktree.
- Read-only `pyproject.toml`: blob
  `c42548df26c483a17f25b1a8040f2419964a2c90`.

## Contract And Gates

Require exact ordered dependency strings, an explicit compatibility-export
header, unique PEP 503-normalized names, valid string/name shape, no unsupported
directive lines, UTF-8, and one terminal newline. Do not hard-code current
versions or counts. `docs/testing.md` should state only canonical/export
ownership and the drift test.

Run focused dependency, Cycle 0001 config, and runtime-env suites; compileall;
allowlisted tracked and new-file whitespace checks; and full discovery. Use the
known empty `service/__init__.py` as `XHS_ENV_FILE` and suppress repository
bytecode. Accept only new passes over the exact 38/10/1 baseline fingerprint.

## Recovery

On task-caused failure, reverse only task hunks and remove the new test after
confirming ownership. Never reset, checkout, or alter the index. Verify all
recorded preimages and Cycle 0001/user-owned hashes. After three failed attempts,
recover and mark `BLOCKED_TECHNICAL`.
