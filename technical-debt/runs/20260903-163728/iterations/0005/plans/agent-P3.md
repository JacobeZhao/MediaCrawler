# P3 Scope And Architecture Review

Verdict: `PASS WITH REQUIRED CONSTRAINTS AND CHECKPOINT REGROUPING`.

Keep account-service and account-pool tests as independent R1 checkpoints. Merge
diagnostic reproduction, its test, and both source hunks into one atomic red/green
checkpoint; the red state is evidence, not an accepted intermediate state.

Assert only source-evidenced rollback and externally meaningful order. Do not
invent behavior for raised pool/status/wake failures, failed restoration,
post-insert QR rollback, cooldown-to-ready, dictionary fairness, or concurrency
atomicity. Preserve every response key/status and the legacy QR cookie field.

The proxy fix adds the canonical redactor and sanitizes only exception text
while retaining the class prefix and 500-character persistence cap. The crawler
fix sanitizes only the QR pong error interpolation; its existing log, flow,
cookie, and state stay unchanged. Split/reject on any broader source edit,
policy change, real external/default-path access, nondeterministic concurrency,
or import-stub leak.
