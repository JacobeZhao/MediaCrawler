# P3 Scope And Architecture Review

Verdict: `PASS WITH REQUIRED CONSTRAINTS`.

Keep the three-checkpoint batch combined and test-only. Frontend checks must
distinguish literal `$()` references from dynamic calls, recognize only the
evidenced API helper chain, normalize path segments without claiming full JS
parsing, and compare a hard-coded frontend-used subset with static backend
routes.

Export tests substitute only unavailable `aiosqlite`; installed openpyxl and
Pillow remain real. The substitute must be child-process scoped or restore
every module/package preimage exactly. Characterize existing behavior only; do
not add or freeze byte, pixel, redirect, decode, concurrency, or destination
policy.

Facade assertions must require uniqueness and an evidence-backed symbol subset,
not exact/exhaustive `__all__` closure. `service.app` is static-only. The remote
JustOneAPI denylist excludes local browser/account/rate/circuit infrastructure
but permits its current shared domain, store, and service DB dependencies. The
local executor must not depend on JustOneAPI provider/client code.

Split or reject any checkpoint that requires a production/dependency/user edit,
real DB/network/browser/proxy access, unsupported public-API decision, or
cannot restore process-global state exactly.
