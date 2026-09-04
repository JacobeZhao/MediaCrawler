# Cycle 0001 Input

- HEAD: `f7f99aeff476c3cbe2959cbc69130a02918c57ce`
- Tracked coverage: 130/130 baseline paths, 0 exact omissions
- User-owned paths: `service/runtime_lock.py`, `service/static/app.js`, `service/static/index.html`, `service/static/styles.css`
- Run-owned path: `technical-debt/runs/20260903-163728/**` (migrated under the updated workflow)
- Protected/excluded boundaries: unchanged from run state; no contents inspected
- Dependency baseline: 13 matching direct declarations, no lock; local `.venv` broken
- Verification baseline: fallback 35 pass, 10 import errors, 1 dependent failure; missing SQLAlchemy/aiosqlite/Playwright
- Goals: 5 UNSATISFIED, 4 PARTIAL, 2 BLOCKED
- Stale evidence: none; HEAD and dirty ownership unchanged since discovery
- Authorized candidates: tests/documentation/scripts and reversible source refactors preserving behavior; no installation, network, real DB, protected, product-policy, or user-owned hunk changes
- Required wave: independent A1-A3 analysis; select the smallest coherent batch with exact oracle and recovery
