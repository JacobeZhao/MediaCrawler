# Cycle 0004 Execution Plan

## Scope, Writer, And Recovery

E1 is the only repository writer. Exact product allowlist:

- create `tests/test_frontend_contract.py`;
- create `tests/test_export_service_contract.py`;
- create `tests/test_architecture_contract.py`.

Every other product path is read-only. Each new file has an R1 nonexistence
preimage and is an independent recovery checkpoint. Recover only the failing
new file after exact ownership confirmation; never checkout/reset or change the
index.

Pin HEAD `f7f99aeff476c3cbe2959cbc69130a02918c57ce`, an empty index,
the four recorded user-owned hashes, frontend/static hashes, export/note/service
DB hashes, all seven route hashes, and the domain/executor/provider/schema/config
/XHS/app facade hashes recorded by P2/P3 and the coordinator.

## Checkpoint 1: Frontend Contract

Create four standard-library tests. Assert unique HTML IDs and resolved
`for`/ARIA/`data-close` references; compare an explicit hard-coded literal JS ID
manifest with the HTML IDs; assert exact static assets and task type/mode/provider
domains; compare a hard-coded frontend-used `(method, normalized path)` set with
both statically parsed JS helpers and AST-parsed route prefixes/decorators; and
assert an explicit set of interactive state classes exists in CSS.

Only literal/evidenced JS helper forms are supported. Dynamic calls must be
classified rather than silently read as literals. Normalize each JS `${...}`
or FastAPI `{...}` path segment to `{param}` while preserving methods, slashes,
and query handling. Do not execute JS, import FastAPI, require every backend
route to have a frontend caller, or edit user-owned static files.

Focused oracle: 4/4.

## Checkpoint 2: Export Contract

Create six parent unittest methods with no top-level export-service import.
Each behavior case runs in a bounded `sys.executable -B -c` child with repository
cwd/PYTHONPATH, dedicated temporary `empty.env` and pycache, `shell=False`, text
capture, 10-second timeout, and exact cleanup. Only the child's unavailable
`aiosqlite` import is replaced; its `connect` fails if unmocked. Use real
openpyxl/Pillow, explicit temporary image/cache paths, and mocked URL/DB access.

Cover cached bytes/no fetch; HTTP-to-HTTPS, headers, timeout 8, exact returned
and cached bytes; exception-to-None/no artifact; first-ten ordered image paths
and fallback cells; exact parameterized note query/dictionary result; and tag
ordering, fixed headers, rewound valid workbook bytes. No real network, DB,
thread, configured/default data path, or resource/destination policy change.
The parent process must retain its exact module-table state.

Focused oracle: 6/6.

## Checkpoint 3: Architecture Contract

Create four standard-library tests using AST and bounded dependency-safe child
imports. Assert hard-coded evidenced facade symbol subsets and uniqueness,
eager bindings and lazy executor branches; dependency-safe domain/eager executor
imports without browser/account/DB infrastructure; positive and negative
provider/executor dependency edges; and route-to-accessor ownership without
direct service/executor/provider imports or raw SQL.

Do not freeze facade exports as exhaustive, import `service.app`, access lazy
concrete executors during smoke checks, reject JustOneAPI's legitimate shared
domain/store/service DB edges, or define a new public API policy.

Focused oracle: 4/4.

## Batch Gates

After each focused gate, run all three new suites together, then the existing 34
focused tests. Run `python -B -m tools.verify`, direct full discovery,
`git diff --check`, UTF-8/BOM/newline/trailing-space checks, exact scope/index,
all pinned hashes, and excluded/protected/default-runtime-path metadata checks.

Projected broad result is 80 outcomes, 69 passes, the same 10 dependency import
errors and 1 dependency-caused failure from only `sqlalchemy`, `aiosqlite`, and
`playwright`. No skip or expected failure is allowed. Any additional failure,
stub leak, hang, path creation, network/DB access, hash drift, or scope change
rejects or revises the affected checkpoint.

No production/documentation/dependency/user edit, install, network, real DB,
browser/proxy, protected-content access, migration, product/security decision,
commit, push, or deployment is authorized.
