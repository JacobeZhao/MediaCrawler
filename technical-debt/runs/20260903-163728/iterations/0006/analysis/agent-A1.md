# Cycle 0006 A1 Gap And Structure

Fresh read-only analysis found import-time composition in `service/dependencies.py`: compatibility config mutation and construction of browser, client, executor, queue, and service objects. `service.app:app` and route accessors are compatibility boundaries. A1 proposed a `TD-003` composition batch but requires import/lifecycle contracts proving zero construction, directory creation, or config mutation on import and exactly-once lifespan cleanup. Persistence and content SQL extraction were considered unready without dependency-capable equivalence gates.

Risk: medium-high; confidence: medium-high. No repository write or protected/external access occurred.
