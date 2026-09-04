# P2 Verification And Recovery Plan

The writable allowlist is exactly the three new tests, each R1 with an absent
preimage and independently recoverable by removing only that file. HEAD must
remain `f7f99aeff476c3cbe2959cbc69130a02918c57ce`; the index stays empty.

Frontend parsing must use explicit manifests, fail on unsupported literal call
forms, normalize JS/FastAPI placeholders segment-wise, and neither execute JS
nor import FastAPI. Export behavior must run with explicit temporary paths and
mocked URL/DB access. Any unavailable-import substitute must be contained in a
bounded child process, with the parent module table unchanged. Architecture
checks use AST and dependency-safe imports only.

Run each focused suite, the existing 34 focused tests, `python -B -m
tools.verify`, direct broad discovery, and diff/encoding/scope/index/hash gates.
For 14 new methods, the expected current-environment result is 80 outcomes, 69
passes, exactly 10 import errors and 1 dependent failure, with missing modules
only `sqlalchemy`, `aiosqlite`, and `playwright`. Any stub leak, real network/DB,
default runtime path, hang, new failure, or fingerprint change rejects the
affected checkpoint.

All pinned production, route, facade, and four user-owned hashes must remain
unchanged. Recovery never uses checkout/reset or changes the index.
