# Cycle 0006 P3 Scope And Architecture Plan

Verdict: `SAFE_TO_IMPLEMENT`; risk medium, confidence 0.86.

Keep `service_db` as the unchanged public/schema/SQL facade. Only the new account adapter may import it. Preserve leading constructor arguments and add optional trailing repository arguments to AccountPool, AccountService, and QrSessionService. QR proxy validation must use the injected adapter. Dependencies wires one shared adapter without changing other construction order or import-time behavior.

Exclude main/app/routes/executors/task manager/proxy service/crawler engine, task/proxy CRUD/content persistence, SQL/schema/path changes, runtime composition, and all user/protected paths. Reject if implementation requires broader exemptions, copied enum definitions, concrete dependency execution, or another production caller change.
