# A1 Gap And Structure

Read-only analysis; no repository file changed.

`TD-003` remains a real structural gap: `service/dependencies.py` mutates
compatibility configuration and constructs the engine, pool, HTTP client,
queues, manager, and services at import; `service.app` calls `create_app()`,
which creates the image directory. A1 proposed explicit runtime composition,
but rated it medium-high risk because route accessors and startup/cleanup order
would all change while dependency-backed lifecycle tests cannot collect in the
current environment.

`TD-004` and `TD-005` remain blocked from safe extraction by incomplete
temporary persistence/query characterization and unavailable `aiosqlite` and
SQLAlchemy. `TD-006` remains ordered behind the content boundary. `TD-001`
lock/provisioning and `TD-009/010` policy portions remain outside authority.

A1 identified ready characterization work for operational repositories and
export/image behavior but rejected inventing byte/concurrency thresholds without
evidence. Suggested production-refactor recovery would be R1, but the current
verification limitation makes composition a deferred candidate, not a ready
Cycle 0004 batch.
