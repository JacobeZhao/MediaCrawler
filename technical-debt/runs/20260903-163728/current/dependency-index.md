# Live Dependency Index

## Cycle 0001 Refresh

Runtime dependency direction remains as recorded by C3; no runtime import,
package declaration, or caller edge changed. The only new source path is
`tests/test_config_contract.py`, which imports `ast`, `re`, `subprocess`,
`unittest`, and `pathlib` from the Python standard library. It reads
`config/settings.py`, `.env.example`, and `docs/config.md`, and invokes bounded
Git metadata commands for `.gitignore` behavior. It is not imported by runtime
code and adds no external dependency or cycle.

## Cycle 0002 Refresh

Runtime imports and dependency values remain unchanged. `pyproject.toml` is the
canonical direct dependency list and `requirements.txt` is its exact ordered
compatibility export. New `tests/test_dependency_contract.py` imports only
`collections`, `pathlib`, `re`, `tomllib`, and `unittest`; it reads the two
manifests and is not imported by runtime code. No external edge or cycle was
added.

## Cycle 0003 Refresh

Runtime imports and dependency declarations remain unchanged. New
`tests/test_runtime_lock.py`, `tests/test_image_downloader.py`,
`tests/test_proxy_config.py`, and `tests/test_verification.py` depend only on
standard-library test/process/filesystem facilities and the production modules
they characterize; runtime code does not import them. New `tools/verify.py`
imports only `os`, `subprocess`, `sys`, `tempfile`, and `pathlib`, and invokes
existing verification phases as child processes. It introduces no runtime
package edge, external dependency, or cycle.

## Cycle 0004 Refresh

Runtime imports and declarations remain unchanged. New frontend and architecture
contracts use only standard-library parsing/subprocess facilities. The export
contract uses real declared openpyxl/Pillow inside bounded children and replaces
only unavailable `aiosqlite` inside those child processes; no substitute enters
the parent test process. The three tests read existing static, route, facade,
provider, executor, and export boundaries but are not imported by runtime code.
No external runtime edge or cycle was added.

## Cycle 0005 Refresh

Three new contract tests use standard-library parent harnesses and bounded
child stubs to exercise real account service, account pool, proxy service, and
crawler methods. Runtime declarations are unchanged. `proxy_service.py` now
imports the already-canonical `tools.redaction.redact_sensitive_text`; the same
dependency edge already exists in other service modules, and crawler engine
already imported that helper. No external dependency, reverse provider edge,
or cycle was added.

## Cycle 0006 Refresh

`service/repositories/accounts.py` is now the only concrete account boundary to
`service.service_db`, using dynamic exact delegation for ten account/candidate/
proxy-read operations. Account pool/service modules depend on the adapter, and
the composition module injects one shared instance. No external dependency,
reverse edge, SQL/schema/path change, or cycle was introduced.
