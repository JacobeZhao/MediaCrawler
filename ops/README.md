# Operations

This directory contains Windows-oriented operational helpers. The application
entry point remains `start_xhs_service.py` in the project root.

## Start Modes

Foreground service:

```powershell
.\ops\start-windows-foreground.cmd
```

Supervised service:

```powershell
.\.venv\Scripts\python.exe .\ops\supervisor_windows.py
```

Both launch modes load the repository-root `.env`. Existing process variables
take priority over that file. The supervisor restarts the service if it exits.
Configure it with:

- `HOST`: service bind host, default `0.0.0.0`
- `PORT`: service bind port, default `8088`
- `XHS_PYTHON`: supervisor child Python, default `.venv\Scripts\python.exe`
- `XHS_LOG_DIR`: log directory for both wrappers, default `logs`
- `XHS_RESTART_DELAY_SECONDS`: supervisor restart delay, default `5`

Set `XHS_ENV_FILE` in the parent process to select a different environment file.
Relative paths are resolved from the repository root, and a selected file must
exist. Both Windows wrappers intentionally pass `--headless`; use
`python start_xhs_service.py` without that flag when a headed browser is required.
The foreground CMD must choose its redirection directory before Python starts,
so its `XHS_LOG_DIR` must be inherited from the parent process; values inside
`.env` still configure the Python service itself.

## Logs

Runtime logs are written under `logs/` by default:

- `service-foreground.log` and `service-foreground.err.log` for the foreground CMD
- `service-<port>.log` and `service-<port>.err.log` for the supervisor
- `service-supervisor.log`

Logs are runtime artifacts and are ignored by Git.
The Windows supervisor rotates each log at 20 MiB and retains five backups
(`.1` through `.5`).

## Health Checks

Use these endpoints after starting:

```text
GET /healthz
GET /readyz
GET /api/status
GET /api/tasks
GET /api/accounts
```

## Account Import

To import tab-separated account files containing cookie JSON in the last column:

```powershell
.\ops\import_xhs_cookie_file.ps1 -Path C:\Users\Administrator\xhs_accounts.txt
```

Use `-ApiBase http://host:port` when importing into a remote service.

## Deployment Notes

Deploy source code and static assets, but exclude runtime state:

- `.env`
- `.venv/`
- `data/`
- `browser_data/`
- `exports/`
- `logs/`
- `database/*.db`

Before replacing code on Tianyi Cloud, keep any temporary rollback copy outside
the project directory and remove it after the deployment is verified. Do not
delete browser account directories unless login state can be recreated.
