# Cycle 0009 Analysis Merge

The user-requested three-agent cleanliness review doubles as the required fresh Cycle 0009 analysis wave. See `cleanliness-audit.md` for the merged repository assessment.

Select policy-free atomic export-cache publication for planning. Two reviewers independently rank it first; the structure reviewer ranks operational repositories first but agrees export handling is ready and has a distinct recovery/oracle boundary. The export batch is the smallest change that converts existing characterization into actual risk reduction without a product or security policy decision.

Expected scope for planning is `service/services/export_service.py` and `tests/test_export_service_contract.py`. Preserve returned bytes, cache path, valid output, HTTP behavior, and existing cache-hit behavior. Publish fetched cache bytes through a same-directory temporary file and `os.replace`; write/close/replace failures must return the current failure result and leave neither a partial final file nor an attributed temporary file. Do not add scheme, redirect, size, content-type, decode, concurrency, or destination policy in this batch.

Planning must define the exact current preimages, cleanup ownership, collision-safe temporary naming, fixed parent-test count, focused/broad totals, failure matrix, Windows semantics, and R1/R2 recovery. Runtime composition, operational repositories, content persistence, attribution, migration, and security decisions remain separate.
