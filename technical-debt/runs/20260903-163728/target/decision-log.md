# Target Decision Log

## Adopted

- Incremental hardening of the existing layout and single-process architecture.
- Reproducible verification before structural work.
- Characterization-first changes with existing compatibility facades retained.
- Explicit lifecycle composition without a DI framework.
- Narrow operational/content persistence ownership without schema/path/ORM changes.
- Explicit attribution, config/docs/artifact parity, bounded resource handling, and migration/recovery governance.
- Decision records rather than guessed outcomes for security, release version, real data, and external contracts.

## Rejected Or Deferred

- T1's broad `shared/`, `tools/cli/`, `service/local_xhs/`, `vendor/`, and test-tree moves are deferred: current layout is reachable and moves add compatibility cost before stronger goals are satisfied.
- Wholesale `src/`/DDD restructuring, new DI framework/message bus, multi-process queue, ORM/database merge, frontend framework/build chain, container platform, and telemetry stack lack repository requirements.
- File size, age, TODOs, generic names, and low static references are not acceptance criteria.
- Repository-wide lint/type cleanup is rejected until a scoped zero-error report-only baseline exists.
- Authentication/CORS, candidate response, encryption, bind address, SSRF destination, canonical version, and destructive migration choices are blocked pending authority.
- Compatibility exports and stealth asset bytes are retained until external consumer/provenance evidence exists.
