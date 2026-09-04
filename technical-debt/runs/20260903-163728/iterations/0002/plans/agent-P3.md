# P3 Scope And Architecture Review

Verdict: `PASS` with a three-path allowlist:

- `requirements.txt`
- `docs/testing.md`
- new `tests/test_dependency_contract.py`

Exact ordered equality is appropriate because the export is a direct
compatibility artifact; it detects specifier, marker, extra, URL, case,
whitespace, and ordering drift. Use `tomllib`, ignore only blank/full-comment
export lines, and separately reject duplicate normalized project names.

Keep out all dependency value changes, `pyproject.toml` edits, locks,
installation/network, verification driver/CI, versioning, runtime code,
user-owned files, and protected paths. `TD-001` and `TD-011` remain `PARTIAL`.
