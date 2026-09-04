# Cycle 0002 Analysis Merge

## Reconciliation

All analysts agree that runtime composition, persistence, attribution, real
migration, resource-policy, and security/release changes are not ready. They
also agree that the next batch should be dependency-free, R1-recoverable, and
avoid runtime and user-owned source.

A1 and A2 independently rank direct dependency-manifest parity first. A3 ranks
runtime-lock characterization first. Both are valid, but `TD-001` is a P0
prerequisite for the broadest set of later goals and its current duplicate
manifests have no mechanical relationship. Runtime-lock characterization is
retained as the next ready candidate.

A1's combined verification-driver proposal is split: it has a separate
invariant and failure oracle, and the unavailable dependencies guarantee its
default full mode cannot pass. This cycle accepts only manifest parity, matching
A2's smaller proposal.

## Accepted Candidate

Advance `TD-001` and `TD-011` by establishing `pyproject.toml` as the canonical
direct dependency declaration and mechanically checking `requirements.txt` as
an exact compatibility export.

- Candidate paths for planning: `requirements.txt`, new
  `tests/test_dependency_contract.py`, and only the minimum existing
  documentation necessary to state ownership.
- Callers/consumers: pip-compatible installation, package metadata, local
  verification documentation, and future CI/verification entry point.
- Invariant: no dependency name, order, specifier, install behavior, or runtime
  behavior changes. `[project].dependencies` is canonical; the export matches
  its ordered strings exactly and has no duplicate normalized project names.
- Oracle: standard-library `tomllib` and text parsing; focused test passes;
  Cycle 0001 focused tests remain green; compileall/diff-check pass; full
  discovery adds only new passes to the established 38/10/1 result.
- Recovery: R1 exact tracked preimages plus new-test nonexistence.
- Risk/confidence: low/high.
- Explicit exclusions: no lock generation, installation, network, verification
  driver, runtime source, user-owned path, protected content, or product choice.

## Rejected Or Deferred

- Unified verification driver: split for a future independent cycle.
- Runtime-lock and image characterization: ready follow-up candidates.
- Public export manifest: external-consumer scope unresolved.
- All structural/runtime/persistence/policy work: prerequisite or authority
  blocked.
