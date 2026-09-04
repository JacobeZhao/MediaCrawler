# Live Current State

After accepted Cycle 0008, HEAD remains
`f7f99aeff476c3cbe2959cbc69130a02918c57ce` with four pre-existing
`USER_OWNED` modifications. The cleanup owns the accepted configuration and
dependency/verification-contract paths plus `technical-debt/**`.
Recursive current coverage is 149/149: all 130 baseline tracked paths plus nineteen
accepted new test/tool paths. The immutable discovery state remains the
baseline anchor.

`config/settings.py` remains the canonical typed application configuration.
`.env.example` now covers all 47 AST-discovered application environment inputs
plus the blank historical `XHS_COOKIES` placeholder. `docs/config.md` names all
active inputs and separates application settings from the parent-process
selector and supervisor-owned inputs. Three standard-library tests mechanically
check sample/default/docs parity and representative artifact exclusions.

`pyproject.toml [project].dependencies` is explicitly canonical and
`requirements.txt` is its checked pip-compatible exact ordered export. Three
standard-library tests enforce exact strings, text/header/newline shape, and
unique PEP 503-normalized distribution names. No dependency value or runtime
edge changed.

Cycle 0003 adds deterministic characterization for cross-process runtime-lock
contention/reacquisition, image download/cache/atomic-write behavior, and proxy
normalization/masking. `python -m tools.verify` is now the canonical
standard-library verification orchestrator and runs dependency/configuration
contracts, compileall, and full discovery in an isolated temporary environment.

Runtime source, dependency declarations and direction, public behavior, data,
and external state are unchanged. The documented `.venv` remains broken.
After Cycle 0003, fallback Python 3.12.13 discovered 66 outcomes: 55 pass, 10 dependency import
errors, and 1 dependency-caused failure. `sqlalchemy`, `aiosqlite`, and
`playwright` remain unavailable; the unified verifier therefore returns 1
after honestly executing every phase.

Cycle 0004 adds static, dependency-light contracts for the user-owned frontend's
DOM/API/CSS references, current export cache/request/query/workbook behavior,
and package facade/provider/route dependency boundaries. Export behavior runs
only in isolated child processes with temporary paths and mocked external
edges. No production import, route, persistence, resource, or UI behavior
changed. Full discovery now has 82 outcomes: 71 pass with the same accepted
10 import errors and 1 dependent failure.

Cycle 0005 adds isolated contracts for account-service orchestration,
account-pool identity/lifecycle/cooldown behavior, and diagnostic redaction.
The proxy-check and QR post-login pong exception paths now reuse the canonical
redaction helper while preserving response keys, cookie projection,
persistence, ordering, and success behavior. Combined focused tests are 64/64.
Full discovery now has 96 outcomes: 85 pass with the same accepted 10 import
errors and 1 dependency-caused failure.

Cycle 0006 adds a stateless account repository adapter as the sole account,
candidate, and lifecycle-proxy boundary over unchanged `service_db` functions.
AccountPool, AccountService, and QrSessionService accept compatible optional
repository injection, and dependencies wires one shared adapter. Focused
coverage is 69/69; full discovery is 101 outcomes with 90 passes and the same
10 import errors plus 1 dependency-caused failure.

Cycle 0007 adds eight isolated runtime composition contracts. They characterize
the current singleton graph and accessors, config projection, `service.app:app`
shape, import/filesystem events, enabled and disabled startup, normal teardown,
pre-yield failures, cleanup continuation, and first-error precedence. Focused
coverage is 77/77; full discovery is 109 outcomes with 98 passes and the same
10 import errors plus 1 dependency-caused failure. These are migration
preconditions, not acceptance of import-time side effects as the target.

Cycle 0008 adds a dynamic proxy repository adapter and routes proxy-management
persistence through compatible optional injection. One shared production
adapter is wired without changing account-lifecycle proxy reads or the physical
`service_db` facade. Focused coverage is 82/82; full discovery is 114 outcomes
with 103 passes and the unchanged ten import errors plus one dependent failure.
