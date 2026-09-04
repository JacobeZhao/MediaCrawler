# A1 Gap And Structure

## Refreshed Gap

- Coverage is 131/131; runtime dependencies and import direction are unchanged.
- `pyproject.toml` and `requirements.txt` duplicate the same 13 direct
  dependencies, with no mechanical parity check, lock, or unified verification
  entry point. The broken environment and unavailable dependencies still block
  the complete `TD-001` oracle.
- Runtime composition, persistence, attribution, resource handling, and public
  facade work all require prerequisite characterization or unavailable
  dependencies. No deletion or directory move is justified.

## Ranked Candidates

1. Advance `TD-001`/`TD-011` by making `pyproject.toml` canonical and checking
   `requirements.txt` as a compatibility export; A1 also proposed a unified
   verification driver. Affected paths: `requirements.txt`, verification docs,
   and new standard-library tests/driver. R1, low risk, high confidence.
2. Add cross-process runtime-lock characterization for `TD-002` without editing
   the user-owned implementation. R1, low-medium risk, high confidence.
3. Characterize image downloading for `TD-002`/`TD-008` with fake responses and
   temporary paths. R1, medium risk, high confidence.
4. Defer composition, operational/content persistence, attribution, fixture
   migration, and public-import restructuring until prerequisite gates and
   external-consumer evidence exist.

## Recommendation

A1 recommended combining the checked dependency export with a unified
verification entry. Exact checks would parse TOML with `tomllib`, compare ordered
requirements, verify driver ordering/failure propagation, run a manifest-only
mode, and reproduce only established broad dependency failures. Lock generation
and installation remain unauthorized.
