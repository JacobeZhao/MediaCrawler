# P2 Verification And Recovery Plan

Pin HEAD, empty index, user hashes, and the exact source preimages. New tests
have R1 nonexistence recovery. Proxy and crawler corrections have R1 exact-hunk
recovery from blobs `975911bb82547f13ad9390e31c4bdfa28937d711` and
`395c7197ab75116efd7fdde1af297568268af232`; never reset/checkout or alter the
index.

All test targets execute only in bounded children. Parent module tables remain
unchanged; unplanned DB connects, HTTP clients, browser constructors, threads,
and paths outside the temporary root fail immediately. Protected/runtime roots
receive metadata-only checks.

Require diagnostic red proof before source edits, then 2/2 green. Run account
service/pool focused suites, all 14 new tests, prior focused 50/50, verifier and
direct discovery. Final expected focused is 64/64 and broad is 96/85/10/1 with
only missing SQLAlchemy/aiosqlite/Playwright. Require diff, encoding, scope,
index, hash, sentinel-free output, and no-default-path gates.
