# T1 Repository Information Architecture

## Target

Retain established `service/{routes,schemas,services,domain,executors,providers,static}` and root bootstrap/docs. Incrementally establish explicit homes for operational persistence (`service/persistence/`), local XHS orchestration (`service/local_xhs/`), content persistence (`database/`), shared production helpers (`shared/`), operator-only CLIs (`tools/cli/`), and attributed vendor assets (`vendor/`). Old import/script paths remain thin compatibility facades until consumer evidence permits removal. Active inherited `base/`, `cache/`, `model/`, and `media_platform/xhs/` remain in place; wholesale renaming is not justified.

Runtime/generated/protected paths remain outside source ownership. No HTTP, task/provider, schema/data, listener, single-process, frontend, or external-integration behavior may change through structural moves.

## Candidate Goals

- `T1-IA-001` (P0/PARTIAL): classify every root child exactly once as source, docs, vendor, durable run evidence, runtime, generated, protected, or compatibility. Oracle: reconciled root inventory and deployment exclusions.
- `T1-IA-002` (P0/UNSATISFIED): content SQL implementation only under `database/`; operational SQL only under `service/persistence/`; facades contain no business logic. Oracle: static SQL/import inventory plus schema/content/task repository tests.
- `T1-IA-003` (P1/UNSATISFIED): production helpers live in `shared/`, operator executables in `tools/cli/`. Oracle: no production import from CLI modules, documented wrappers, compile/redaction/CLI-help gates.
- `T1-IA-004` (P1/UNSATISFIED): local browser/account/crawl infrastructure has an explicit `service/local_xhs/` boundary. Oracle: service root contains composition only and old imports are tested facades; local/remote queue behavior unchanged.
- `T1-IA-005` (P0/UNSATISFIED): each wildcard/lazy/legacy surface has supported symbols, consumers, and retention/removal criteria. Oracle: compatibility manifest plus public-import tests and zero new business logic in facades.
- `T1-IA-006` (P1/UNSATISFIED): tests are classified as unit, hermetic integration, or opt-in external contract. Oracle: discovery parity and a default hermetic clean-environment suite with no silent skips.
- `T1-IA-007` (P1/BLOCKED): runtime third-party assets have origin, license, version/checksum, and update path. Oracle: metadata/checksum/loader gate; blocked on stealth asset provenance.

## Ordering And Recovery

Add characterization/import gates first; extract shared helpers; split operational persistence behind the existing module; consolidate content queries/writes behind the existing store API; move local modules one at a time; then reclassify tests/CLIs. Vendor movement waits for provenance. Remove no facade without internal-zero plus external-consumer evidence. Tracked clean files use exact-preimage `R1`; user-owned files remain excluded; migrations/data changes remain blocked without separate recovery authority.

Status: independent proposal complete; not adopted until T2-T5 reconciliation.
