# A2 Behavior And Risk

Read-only fresh analysis; no files changed.

A2 found two concrete credential diagnostic leaks. Proxy check stores and
returns `type: raw exception` even though proxy URLs may contain credentials.
Post-login QR verification logs a redacted exception but returns the raw
exception in its error field. `tools/redaction.py` is already the canonical
bounded redactor, and `docs/technical-debt.md` states that runtime diagnostics
and persisted errors redact credential-bearing content.

A2 recommended two narrow R1 source checkpoints in
`service/services/proxy_service.py` and `service/crawler_engine.py`, plus a new
dependency-isolated diagnostic contract. The oracle preserves current status,
keys, persistence, retry, and success behavior while proving sentinel secrets
are absent from returned, persisted, and logged diagnostics. No real secret,
network, DB, browser, profile, or policy decision is needed.

A2 judged runtime composition ready only for more characterization, not
production extraction. Persistence/content/attribution work remains blocked by
unavailable dependencies, and resource thresholds/security-release decisions
remain outside authority.
