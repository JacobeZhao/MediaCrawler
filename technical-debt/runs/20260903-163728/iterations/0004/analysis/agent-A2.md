# A2 Behavior And Risk

Read-only analysis; no repository file changed.

A2 recommended two dependency-free, test-only R1 checkpoints. First, a new
frontend contract test should use standard-library parsing to verify unique DOM
IDs, label/ARIA references, literal JavaScript element lookups, and normalized
frontend API templates against route declarations without importing FastAPI or
editing the user-owned static files. Second, an export-service contract test
should characterize cache precedence, HTTP-to-HTTPS normalization, headers,
timeout, exact bytes, the ten-image order/limit, fallback cells, and isolated
failures using temporary paths and mocks only.

A2 explicitly rejected resource enforcement, destination policy, composition,
persistence extraction, attribution rewiring, security/release decisions, and
dependency locking in this snapshot. Export import isolation may stub only the
unavailable `aiosqlite` module inside a bounded child or isolated test context;
the stub must not leak into broad discovery. Expected broad counts increase
only by the new passing methods while the 10/1 dependency fingerprint remains.
