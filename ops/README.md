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

The supervisor restarts the service if it exits. Configure it with environment
variables:

- `HOST`: bind host, default `0.0.0.0`
- `PORT`: bind port, default `8088`
- `XHS_PYTHON`: Python executable path, default `.venv\Scripts\python.exe`
- `XHS_LOG_DIR`: log directory, default `logs`
- `XHS_RESTART_DELAY_SECONDS`: restart delay, default `5`

## Logs

Runtime logs are written under `logs/` by default:

- `service-8088.log`
- `service-8088.err.log`
- `service-supervisor.log`

Logs are runtime artifacts and are ignored by Git.

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
- `archive/`
- `data_archive/`
- `logs/`
- `database/*.db`
- `_backup_before_cleanup_*/`

Before replacing code on Tianyi Cloud, keep a timestamped backup of the current
project directory and do not delete browser account directories unless login
state can be recreated.

`data_archive/` is retained only as local migration evidence and recovery
material. It is not part of the active source tree.
