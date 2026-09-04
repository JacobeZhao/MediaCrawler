# T3 Configuration, Tooling, And Operations

## Target Ownership

`runtime_env.py` owns strict atomic env loading; `config/settings.py` owns complete typed defaults/parsing/validation; launchers own CLI/process lifecycle only; legacy config modules are projections only. `pyproject.toml` is canonical direct dependency/project metadata, `requirements.txt` is generated or parity-checked compatibility output, and a lock artifact owns transitive resolution. `.env.example` and config docs are mechanically checked against settings. One repository verification command runs parity, compile, then deterministic tests and is called unchanged by CI. Windows operations retain the one-process/runtime-state contract.

No container, frontend build system, remote telemetry stack, or repository-wide lint/type rewrite is justified. Lint/type remain non-blocking until a clean scoped baseline exists.

## Candidate Goals

- `T3-G01` P0/UNSATISFIED: every env input has one typed definition and synchronized non-secret sample/docs. Oracle: settings/schema parity plus env/startup tests.
- `T3-G02` P0/PARTIAL: settings can be constructed from injected mappings and validate before resources start. Oracle: import/invalid-value tests without secret output; no new rejection without characterization.
- `T3-G03` P0/UNSATISFIED: canonical dependencies plus reproducible lock and generated/parity-checked requirements. Oracle: clean install collects all 91 declared tests without dependency import errors. Installation itself remains separately controlled.
- `T3-G04` P0/UNSATISFIED: one deterministic local/CI command runs parity, compile, and hermetic tests. Oracle: clean Windows CI invokes the same command with no secrets/runtime DB/browser/live provider.
- `T3-G05` P2/PARTIAL: lint/type policy prevents speculative churn. Oracle: explicitly non-blocking until report-only scoped zero baseline, then touched-code ratchet.
- `T3-G06` P0/BLOCKED: one canonical package/runtime/API version. Oracle: chosen value derives/parity-checks metadata, OpenAPI, and `/version`; release-owner decision required.
- `T3-G07` P1/PARTIAL: bounded Windows supervisor/restart/rotation/shutdown and single-process smoke evidence. Oracle: focused tests plus documented health checks; no real deployment.
- `T3-G08` P0/PARTIAL: mechanical source/runtime deployment separation. Oracle: manifest and `git check-ignore` tests include live `cache/*.py` but exclude protected/generated roots.
- `T3-G09` P1/PARTIAL: existing logs/health/task/audit observability is tested and redacted. Oracle: endpoint/readiness/log/audit/rotation tests and retention/diagnosis docs; remote telemetry needs separate authority.

## Constraints

Restore reproducible provisioning before broad gates; characterize before config validation changes; do not guess version or host Python; keep live XHS/JustOneAPI/MySQL/browser checks outside hermetic CI; never inspect, deploy, copy, delete, or migrate protected/runtime content. Code/policy changes are R1; runtime evidence is R2.

Status: independent proposal complete; not adopted until T1-T5 reconciliation.
