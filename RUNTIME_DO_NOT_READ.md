# Runtime Directories

These directories are local runtime state, not source code. Future AI agents
should not inspect them unless explicitly asked for a runtime incident:

- `.venv/`
- `data/`
- `data_archive/`
- `browser_data/`
- `archive/`
- `logs/`
- `_backup_before_cleanup_*/`

`data/private/` may contain account workbooks or other sensitive local inputs.
Do not quote or summarize its contents in normal code work.

For source-level context, start with:

- `README.md`
- `docs/README.md`
- `docs/project-map.md`
- `service/README.md`
- `ops/README.md`
