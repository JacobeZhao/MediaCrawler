# Cycle 0002 Execution Plan

## Invariant And Goals

Advance `TD-001` and `TD-011` without changing dependency resolution or runtime
behavior. `pyproject.toml [project].dependencies` is canonical;
`requirements.txt` is a checked pip-compatible export with the same exact
ordered strings and no duplicate normalized distribution names.

## Conflict Resolution

P1 proposed omitting `docs/testing.md`; P2 and P3 included it. The coordinator
retains one narrow documentation paragraph because `docs/testing.md` is the
repository's verification contract and is the canonical place to tell future
maintainers which manifest to edit. The requirements header remains the local
machine-visible ownership marker. This does not add install, lock, CI, or green
suite claims.

## Writer And Exact Allowlist

E1 is the only repository writer.

- `requirements.txt`: prepend two full-line comments declaring it the checked
  compatibility export of canonical `[project].dependencies`; preserve all 13
  dependency strings and their order exactly.
- `docs/testing.md`: add a short dependency-manifest contract stating canonical
  ownership, exact export semantics, and the focused drift test.
- `tests/test_dependency_contract.py`: add standard-library contract tests for
  header presence, UTF-8/text shape, exact ordered equality, and unique PEP
  503-normalized leading project names.

Read-only: `pyproject.toml`. Every other product path is forbidden.

## Recovery

R1 exact preimages:

- `requirements.txt` blob
  `1df7c9713034c6ba95ce131dc7404c7aa3a44fc3`, mode 100644.
- `docs/testing.md` blob
  `1fdc75086bbc64374ae6d482cb12eb28e41d923f`, mode 100644.
- New test nonexistence.

Read-only canonical blob:
`pyproject.toml=c42548df26c483a17f25b1a8040f2419964a2c90`.
Restore only task-owned hunks/new file; never reset, checkout, or alter index.

## Test Contract

Use `pathlib`, `re`, `tomllib`, and `unittest` only. Ignore only blank and
full-line comment export lines, compare full dependency strings exactly in
order, reject directives/malformed names/non-string canonical entries, and
reject duplicate names after lowercase plus `[-_.]+ -> -` normalization. Check
the explicit export header and a single terminal newline. Do not hard-code
versions or dependency count.

## Gates

1. Focused dependency contract: all new tests pass.
2. Cycle 0001 config contract: 3/3 pass.
3. Runtime environment suite: 14/14 pass.
4. Compileall with bytecode suppressed; allowlisted diff/whitespace checks pass.
5. Full fallback discovery adds only the new passes to 38/10/1; remaining
   failures must have the exact unavailable `sqlalchemy`, `aiosqlite`, and
   `playwright` fingerprint.
6. Diff is limited to the three paths plus accepted prior/run docs, index is
   empty, `pyproject.toml`, Cycle 0001 files, and four user-owned hashes are
   unchanged.

Every Python gate explicitly uses empty `service/__init__.py` as
`XHS_ENV_FILE`. No lock, install, resolver, network, DB, browser, protected path,
commit, push, deployment, runtime source, or product decision is allowed.
