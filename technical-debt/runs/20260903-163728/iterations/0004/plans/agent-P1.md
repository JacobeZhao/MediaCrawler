# P1 Change Plan

Create exactly `tests/test_frontend_contract.py`,
`tests/test_export_service_contract.py`, and `tests/test_architecture_contract.py`.
No shared helper, fixture, snapshot, documentation, dependency, production, or
user-owned file is writable.

Frontend: four standard-library methods cover a hard-coded literal JS ID
manifest against unique HTML IDs, static assets and task control domains, a
hard-coded method/path frontend API manifest against independently AST-parsed
route prefixes/decorators, and an explicit set of dynamic CSS state classes.
Template segments normalize to `{param}` without executing JS or importing
FastAPI.

Export: six methods cover cached bytes/no fetch, HTTP-to-HTTPS request metadata
and cache population, failure/no artifact, first-ten image ordering and URL
fallbacks, exact parameterized note query behavior, and sorted/rewound workbook
output. Import the real module only under an isolated `aiosqlite` substitute;
use explicit temporary roots, mocked network/connectors, and real installed
openpyxl/Pillow.

Architecture: four methods cover evidence-backed facade symbol manifests and
lazy bindings, dependency-safe facade imports, one-way provider/executor
dependency rules, and route-to-accessor boundaries. Do not import `service.app`
or concrete lazy executors for smoke checks.

Projected new methods: 14. Execute checkpoints frontend, export, architecture;
run each focused file before combined and broad gates.
