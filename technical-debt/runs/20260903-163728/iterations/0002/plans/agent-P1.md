# P1 Change Plan

## Scope

Keep `pyproject.toml` as the canonical list and `requirements.txt` as its
pip-compatible exact mirror. Current 13 dependency strings already match; no
name, order, specifier, installation, or runtime behavior changes.

P1 proposed a two-path writer allowlist: prepend two ownership comments to
`requirements.txt` and add standard-library-only
`tests/test_dependency_contract.py`. P1 considered `docs/testing.md`
unnecessary because broad discovery automatically collects the new test.

## Test Design

- Parse `[project].dependencies` with `tomllib` as ordered nonempty strings.
- Parse the export as UTF-8, ignoring only blanks and full-line comments.
- Assert exact ordered strings.
- Extract and PEP 503-normalize leading distribution names and reject
  duplicates in both lists.
- Use only `pathlib`, `re`, `tomllib`, and `unittest`.

## Recovery And Gates

R1 preimage for `requirements.txt` is
`1df7c9713034c6ba95ce131dc7404c7aa3a44fc3`, mode 100644; the test has a
nonexistence preimage. Focused dependency/config/runtime-env tests, compileall,
allowlisted diff-check, broad discovery, exact scope, empty index, and unchanged
user-owned hashes are required. Expected broad delta is new passes only over
38/10/1.
