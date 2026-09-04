# T4 Quality, Security, And Maintainability

## Target Model

Preserve all documented behavior and compatibility unless an explicit product/security decision authorizes change. Cleanup may add characterization, redaction, bounded resource handling, temporary-DB migration tests, deterministic error mapping, accessibility verification, dependency evidence, and recovery records. Authentication/CORS, candidate-secret projection, encryption, destination policy, canonical version, destructive real-data changes, and live probes remain decision/authority boundaries.

## Candidate Goals

- `T4-G01` P0/PARTIAL: deterministic coverage for HTTP, proxy, image, lock, account, frontend, and local-provider gaps; oracle is clean collection of all 91 tests plus focused and broad gates.
- `T4-G02` P0/BLOCKED: secrets never escape logs/errors/audits/public projections. Oracle uses sentinel traversal; candidate response change is blocked on workflow decision.
- `T4-G03` P0/BLOCKED: explicit mutation/secret endpoint trust boundary. Oracle is an approved threat model plus auth/origin/CSRF HTTP tests.
- `T4-G04` P0/UNSATISFIED: image/export fetches bound scheme, redirects, timeout, bytes, type, decoding, and atomic writes. Oracle uses mock edge cases and unchanged valid-image output.
- `T4-G05` P0/BLOCKED: explicit SSRF destination and redirect policy. Oracle covers DNS/IP/private/loopback/IPv4/IPv6 matrix after product approval.
- `T4-G06` P0/BLOCKED: versioned repeatable recoverable schema evolution. Oracle uses fresh/legacy/interrupted/idempotent fixtures; real DB remains R2.
- `T4-G07` P1/PARTIAL: stable safe error categories preserving cancellation/lease behavior. Oracle maps errors to existing HTTP/task outcomes with no traceback/secrets.
- `T4-G08` P1/PARTIAL: bounded single-process work. Oracle covers existing ceilings, provider independence, image/export bounds, SQLite busy handling, and shutdown.
- `T4-G09` P1/PARTIAL: keyboard-accessible named console with no layout overlap. Oracle uses automated accessibility and interaction checks at 320/768/1440 px; user-owned files require attributable R2 hunks.
- `T4-G10` P0/UNSATISFIED: reproducible reviewable dependencies. Oracle is clean locked collection and manifest/lock parity; upgrades remain separate.
- `T4-G11` P1/PARTIAL: high-risk modules change only behind caller/state characterization and boundary gates, never size-driven rewrites.
- `T4-G12` P0/PARTIAL: every batch records exact preimage, allowlist, R-class, gates, restore recipe, and unchanged protected/user paths.

Status: independent proposal complete; not adopted until T1-T5 reconciliation.
