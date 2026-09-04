# A1 Gap And Structure

Read-only fresh analysis; no files changed.

A1 proposed making `TD-003` the batch center: introduce a lifespan-owned runtime
container, turn `service/dependencies.py` into an installed-container accessor
facade, remove import-time compatibility mutations/construction, and move status
aggregation into a service. Evidence confirms the gap: dependencies constructs
the engine, pool, HTTP client, registry, manager, and services at import, while
`create_app()` creates the image directory.

The proposal is medium-high risk across `service/main.py`, every route accessor,
startup/cleanup order, and `service.app:app`. Its key lifecycle tests currently
do not collect without SQLAlchemy/aiosqlite/Playwright. A1 considered sentinel
module isolation sufficient, but confidence in one-attempt execution was only
medium-high. `TD-004/005/006/008` remain deferred by persistence prerequisites,
attribution ordering, or unevidenced resource policy.
