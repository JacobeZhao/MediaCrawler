# C3 Dependencies, Data, And Integrations

## Scope

Read-only AST/import/caller, schema, validation, configuration, secret-boundary, and external-integration mapping at baseline revision. Protected/runtime contents were not opened. One broad search exposed two lines of a user-owned CSS file; no conclusion relies on them.

## Dependency Direction

Launchers -> environment bootstrap -> ASGI composition -> routes -> services -> operational repository/TaskManager -> executor registry -> local crawler or JustOneAPI adapter -> shared content repository. Static AST reconstruction found no multi-module strongly connected component. Hidden coupling instead comes from import-time singleton construction, frozen settings, mutation of wildcard-exported legacy `config` globals, lazy executor exports, ambient `ContextVar` attribution, and dynamically loaded `libs/stealth.min.js`.

## Data And Migration Boundaries

- Content SQLite: SQLAlchemy models/upserts, raw `aiosqlite` reads in note/export/count services, startup duplicate merging and index creation, no migration ledger.
- Service SQLite: inline DDL/additive columns/key rewrites for tasks, provider requests, tags, accounts, proxies, candidates, and events; no schema-version table.
- Browser profiles and image cache: protected filesystem state with create/move/delete/download effects.
- External MySQL: standalone operator ETL with its own environment parser and transaction logic.
- Referential integrity in the service DB is largely procedural; cross-store schema knowledge exists in `service_db` and services.

## Validation And Security Boundaries

Task/provider options are bounded and cross-validated; note filesystem paths and dynamic SQL fields use allowlists/containment checks; proxy URLs separate credentials; environment loading is atomic and avoids value logging; JustOneAPI query tokens are redacted and covered by tests. However, candidate accounts are selected with `SELECT *`, decoded without removing `password` or `cookie_json`, returned by the account service, and exposed by an unauthenticated wildcard-CORS route. Account cookies, proxy passwords, and candidate secrets are plaintext in local SQLite. Remote image downloads accept provider/persisted URLs without destination allowlisting or private-address rejection.

## External Integrations

XHS private HTTP/browser APIs, Playwright Chromium, `xhshow`, JustOneAPI, proxy egress checking, provider image hosts, local HTTP operator tools, external MySQL, and the configured package index are the external boundaries. Static contracts are mapped; no live token/browser/schema/network probe was authorized or run.

## File/Directory Coverage

All 130 tracked files were classified across configuration, persistence, XHS integration, shared utilities, application layers, provider modules, routes/schemas/services, operations, documentation, and 14 tests. No static dependency cycle was found. The canonical per-file records and exclusions are reconciled in `../coverage-manifest.md`.

## Evidence-Backed Candidates

1. Candidate credential exposure across the HTTP boundary.
2. Ungoverned startup migrations in both SQLite stores.
3. Split physical-schema ownership between repositories and raw-query services.
4. Import-time composition and mutable compatibility configuration.
5. Reproducibility gap from duplicated unlocked dependencies and a broken local environment.
6. Remote image SSRF/cache-poisoning boundary.
7. Plaintext local secret storage with inconsistent public projections.
8. Broad persistence/crawler/provider modules with independent concerns.
9. Missing hermetic fixtures for key external payload/schema boundaries.
10. Unpinned provenance/regeneration for the browser stealth asset.

Open product/authority questions include intended listener trust, frontend need for raw candidate secrets, startup duplicate-deletion policy, public Python APIs, MySQL tool support level, asset provenance, encryption expectations, and real upstream contracts.

Status: `COMPLETE_WITH_OPEN_QUESTIONS`.
