# Cycle 0007 P2 Verification And Recovery Plan

- Verdict: `PASS`.
- Fixed proposal: eight parent tests, `77/77` combined focused, and `109 outcomes / 98 pass / 10 errors / 1 failure` broad discovery.
- Failure matrix: lock construction/acquire, service DB init, sqlite-parent creation, table creation, enabled engine/pool/task-manager starts, disabled task-manager start, every async cleanup, lock release, multiple cleanup errors, and body/startup error precedence.
- Isolation: `subprocess.run` with `shell=False` and timeout; temporary cwd, empty selected env file, bytecode root, home/profile/temp roots; minimal non-secret environment; synthetic infrastructure modules; one structured result; parent module/environment/cwd invariance.
- Accepted broad fingerprint remains only missing `sqlalchemy`, `aiosqlite`, and `playwright` producing the existing ten import errors and one dependent failure.
- Gate order: new file, combined focused, compileall, diff check, unified verifier, direct discovery, exact scope/index/hashes/encoding checks.
- Recovery: confirm absent and untracked preimage, then remove only the exact new file with a narrow patch if recovery is required.
- Revise isolation or assertions rather than installing or touching real infrastructure; block any required production edit or authority expansion.
