# A2 Behavior And Risk

## Risk Findings

- Missing dependencies and lock resolution block a clean broad gate, but the two
  direct dependency manifests can be compared hermetically.
- `service/dependencies.py` constructs runtime objects and mutates compatibility
  configuration at import. Refactoring is premature without startup and
  lifecycle characterization.
- Operational/content persistence and attribution changes have wide schema,
  lease, checkpoint, row-shape, and concurrency risk and depend on unavailable
  packages.
- Image downloader/export reads are unbounded and export cache writes are not
  atomic. Destination policy remains a blocked product/security decision.
- Remaining public-export scope lacks external-consumer evidence. Security,
  release, and real migration decisions remain blocked.

## Ranked Candidates

1. `TD-001`/`TD-011`: check `requirements.txt` as an exact compatibility export
   of canonical `[project].dependencies`; use a standard-library contract test
   and a narrow documentation clarification. R1, low risk, high confidence.
2. `TD-002`: characterize the local image downloader without runtime changes.
   R1, low risk, high confidence.
3. `TD-008`: enforce bounded image reads only after characterization and a
   defensible byte limit. R1, medium risk/confidence.
4. Defer unified verification, composition, persistence, attribution, and
   migrations until their prerequisites can be met.

## Recommendation

Select only dependency compatibility parity. Assert exact ordered strings and
no duplicate normalized names with `tomllib`; explicitly identify
`pyproject.toml` as canonical. Do not generate a lock or install packages.
