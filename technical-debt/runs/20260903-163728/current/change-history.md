# Change History

- Baseline through target merge: created durable workflow documentation only. No product-code edits, deletions, dependency changes, runtime-data operations, commit, push, deployment, network call, or external mutation.
- Cycle 0001 (`ACCEPTED`): synchronized `.env.example` and `docs/config.md`
  with all active `Settings` inputs and added `tests/test_config_contract.py`.
  E2/E3 returned `PASS`; focused tests passed 3/3, runtime-environment tests
  passed 14/14, compileall and diff-check passed, and broad discovery added
  three passes without changing the baseline 10 import errors and 1 dependent
  failure. Recovery uses the R1 blobs recorded in
  `iterations/0001/execution/agent-E1.md`; all user-owned hashes were unchanged.
- Cycle 0002 (`ACCEPTED`): declared `pyproject.toml` canonical, marked
  `requirements.txt` as its checked exact export, documented the focused gate,
  and added `tests/test_dependency_contract.py`. After a one-file CRLF-oracle
  repair, E2/E3 returned `PASS`; dependency tests passed 3/3, Cycle 0001 and
  runtime-env tests stayed green, compile/diff checks passed, and broad
  discovery became 41/10/1 solely through three new passes. R1 blobs are in
  `iterations/0002/execution/agent-E1.md`; user-owned hashes were unchanged.
- Cycle 0003 (`ACCEPTED`): added cross-process runtime-lock, image downloader,
  proxy configuration, and unified verifier characterization; introduced
  `python -m tools.verify` and documented it as canonical. After one repair for
  cross-platform commands, dedicated temporary environment files, and durable
  recovery evidence, E2/E3 returned `PASS`. Focused tests passed 34/34;
  compile/diff checks passed; broad discovery became 55/10/1 through 14 new
  passes while retaining the accepted missing-dependency fingerprint. R1 and
  exact-hunk recovery are recorded in `iterations/0003/execution/agent-E1.md`;
  production and user-owned hashes were unchanged.
- Cycle 0004 (`ACCEPTED`): added three test-only contracts for frontend
  DOM/API/CSS coupling, export cache/request/query/workbook behavior, and
  facade/provider/route dependency direction. E2/E3 initially required stricter
  dynamic-call accounting, segment normalization, wildcard-facade checks, and a
  narrower provider denylist; the final allowed repair closed all findings and
  both returned `PASS`. New tests passed 16/16, total focused tests 50/50, and
  broad discovery became 71/10/1 solely through 16 new passes. R1 recovery is
  recorded in `iterations/0004/execution/agent-E1.md`; production and user-owned
  hashes were unchanged.
- Cycle 0005 (`ACCEPTED`): added 14 isolated account-service, account-pool, and
  diagnostic-redaction contract tests, then reused the canonical redaction
  helper in exactly two exception diagnostics. E2/E3 returned `PASS`; focused
  tests passed 64/64, compile/diff/scope/index/hash gates passed, and broad
  discovery became 85/10/1 solely through 14 new passes. Exact R1/hunk recovery
  is recorded in `iterations/0005/execution/`; user-owned hashes were unchanged.
- Cycle 0006 (`ACCEPTED`): added a stateless account repository adapter and
  routed account pool/service/QR persistence through one shared injected
  instance. E2/E3 returned `PASS`; focused tests passed 69/69 and broad
  discovery became 90/10/1 with only the accepted missing-dependency
  fingerprint. `TD-004` advanced to `PARTIAL`; exact recovery is recorded in
  `iterations/0006/execution/`.
- Cycle 0007 (`ACCEPTED`): added one isolated eight-test runtime composition
  contract. E3's initial `REVISE` exposed test-order coupling; the final allowed
  repair removed it and strengthened cold-import and mount-directory evidence.
  E2/E3 then returned `PASS`; focused tests passed 77/77 and broad discovery
  became 98/10/1 with only the accepted dependency fingerprint. Exact R1
  recovery and all attempts are recorded in `iterations/0007/execution/`.
- Cycle 0008 (`ACCEPTED`): added an injectable proxy-management repository and
  one shared production instance while preserving the account-lifecycle proxy
  read and unchanged `service_db` facade. E2/E3 returned `PASS`; focused tests
  passed 82/82 and broad discovery became 103/10/1 with only the accepted
  dependency fingerprint. Exact R1/R2 recovery is recorded in
  `iterations/0008/execution/`.
