# Immutable Initial Current State

## Baseline And Coverage

The repository is a single-host, single-process FastAPI Xiaohongshu crawler with a no-build operator console, local Playwright provider, optional JustOneAPI provider, two SQLite stores, Windows operations, and a standalone MySQL ETL. Baseline HEAD is `f7f99aeff476c3cbe2959cbc69130a02918c57ce`; all 130 tracked files are mapped in `coverage-manifest.md`. Four pre-existing modified service/frontend files are `USER_OWNED`. Protected/runtime/generated roots were metadata-only.

## Architecture

Launchers load environment configuration before the ASGI composition root. Lifespan acquires a file lock, initializes operational and content schemas, starts configured provider infrastructure, then runs one queue/worker per provider. HTTP routes delegate to application services. `TaskManager` persists leases, heartbeats, retries, checkpoints, and results. Local execution uses account pool -> crawler engine -> XHS browser/client; remote execution uses JustOneAPI transport -> normalizer. Both persist canonical content through `store/xhs`.

Operational SQLite stores tasks, provider audits, accounts, proxies, candidates, tags, and crawl events. Content SQLite stores creators, notes, comments, and source/provider/task attribution. Browser profiles, images, exports, logs, and external MySQL are separate side-effect planes.

## Verified Strengths

Provider-specific queues and identity, resume/recrawl semantics, unknown billed-outcome handling, request budgets, secret redaction, strict environment loading, bounded request schemas, filesystem containment for note images, proxy masking, resilient shutdown, and idempotent content upserts have focused characterization tests. Static Python imports contain no multi-module cycle. Routes, schemas, services, executors, providers, and domain records have recognizable boundaries.

## Evidenced Debt And Risk

1. Candidate account records appear to expose plaintext `password` and `cookie_json` through an unauthenticated wildcard-CORS endpoint.
2. Both SQLite stores perform unversioned startup DDL/data repair; content startup can merge/delete duplicates without a migration ledger or repository recovery artifact.
3. Content physical-schema ownership is split between SQLAlchemy repository writes and raw `aiosqlite` queries in services and task enrichment.
4. Import-time singleton composition, frozen settings, mutable wildcard compatibility config, and ambient attribution context make order and hidden state part of correctness.
5. Crawler, service DB, task manager, JustOneAPI executor, and static JS concentrate multiple independently changing responsibilities.
6. The documented `.venv` is broken; dependencies are duplicated across unlocked manifests and verification is not automated in CI.
7. Remote image fetches trust provider/persisted URLs without a destination policy.
8. Frontend/API selector and field contracts, HTTP integration, proxies, image behavior, runtime-lock contention, account transitions, and broad live protocol behavior lack focused automated gates.
9. Runtime DB output is colocated with database source; `tools/` mixes production libraries with operator CLIs; inherited generic names/public facades obscure ownership.
10. Package/runtime versions disagree, environment examples/docs omit settings, and vendored stealth asset provenance is not reproducible.

## Baseline Verification

The documented `.venv` command cannot launch because it references missing `E:/tmp/Python312/python.exe`. Fallback Python 3.12.13 ran 46 outcomes: 35 passed, 10 test modules failed import, and 1 dependent startup test failed because SQLAlchemy, aiosqlite, and Playwright were absent. There are 91 statically declared test methods. HTTP/browser/live-provider/MySQL gates were unrun because they require provisioned runtime, secrets, network, or external mutation.

## Constraints

Preserve public HTTP/task/provider behavior, local single-process deployment, user-owned edits, compatibility imports, and secret/runtime state. Do not infer dead code from generic names, wildcard/lazy exports, or missing static callers. Authentication/network exposure, canonical release version, credential encryption, destructive migration policy, and live external contracts require product/authority evidence.

This document is the immutable initial state; later corrections must be appended as dated addenda.
