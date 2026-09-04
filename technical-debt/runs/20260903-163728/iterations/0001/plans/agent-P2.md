# P2 Verification And Recovery

R1 preimages: `.env.example` blob `efb74870ce3eb0a48556f218fe21bf93b3442d7f`; `docs/config.md` blob `1877eae8eeed6e085a5a996d040c01f38970e936`; test absent. Preserve user hashes: runtime lock `44620a...15c`, app.js `1eb3d1...6ce0`, index `0e70f7...933e`, styles `940dbb...9ddb`. Focused standard-library test, `git diff --check`, compileall with temp pycache, and full fallback suite; accept exact baseline dependency failures only. Recover task-owned hunks/new file without reset/checkout.
