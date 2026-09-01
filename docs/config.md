# Configuration

Configuration priority:

```text
CLI arguments > existing process environment > root .env > defaults in config/settings.py
```

`start_xhs_service.py`, direct `uvicorn service.app:app` imports, and the Windows
supervisor all load the root `.env` before application settings are created.
Existing process variables are never overwritten, including variables whose
value is an empty string. Variable names are compared case-insensitively so the
same file behaves consistently on Windows.

To load a different file, set `XHS_ENV_FILE` in the parent process before
starting Python. `XHS_ENV_FILE` entries inside an environment file are rejected,
including lowercase variants, so one file cannot redirect a later launcher load.
Relative selector paths are resolved from the repository root. An explicitly
selected file must exist; a missing root `.env` remains an allowed no-op.

`HOST` and `PORT` control the listener when using `start_xhs_service.py` or the
Windows supervisor. A direct `uvicorn service.app:app` command chooses its socket
before importing the app, so pass Uvicorn's own `--host` and `--port` arguments
for that launch mode.

The loader accepts UTF-8 (with an optional BOM), blank lines, comments,
`KEY=VALUE`, and `export KEY=VALUE`. Single- or double-quoted values are literal;
there is no variable expansion, process execution, escape decoding, or multiline
continuation. A malformed file blocks startup without logging its values, and no
variables are applied unless the entire file is valid.

Important variables:

- `HOST`, `PORT`: bind address.
- `HEADLESS`: Playwright headless mode. Both Windows wrappers intentionally
  force this to `true`; start the Python entry point directly for headed mode.
- `CDP_CONNECT_EXISTING`: usually `false` for service mode.
- `XHS_INTERNATIONAL`: default `false`; `true` switches to `rednote.com`.
- `SQLITE_DB_PATH`: crawler content SQLite path.
- `SERVICE_DB_PATH`: service task/account SQLite path.
- `RUNTIME_LOCK_PATH`: single-instance lock path.
- `CRAWLER_MIN_SLEEP_SEC`, `CRAWLER_MAX_SLEEP_SEC`: crawl pacing.
- `LOCAL_CRAWLER_ENABLED`: default `true`; set `false` for a JustOneAPI-only process
  that skips Playwright engine and account-pool startup.

## JustOneAPI Provider

The optional provider is disabled by default. Existing requests continue to use the
`local` provider unless they explicitly send `provider="justoneapi"`.

- `JUSTONEAPI_ENABLED=true`: register/enable outbound JustOneAPI execution.
- `JUSTONEAPI_TOKEN=`: server-side API credential. Required when enabled.
- `JUSTONEAPI_BASE_URL=https://api.justoneapi.com`: upstream API origin.
- `JUSTONEAPI_TIMEOUT_SEC=120`: per-request HTTP timeout in seconds.
- `JUSTONEAPI_MAX_RETRIES=2`: maximum client retries for retryable upstream or
  transport failures.
- `JUSTONEAPI_RETRY_BASE_SEC=2`: base delay used for retry backoff.
- `JUSTONEAPI_MAX_REQUESTS_PER_TASK=100`: server-side request ceiling for one task.

For API-only operation, set both `LOCAL_CRAWLER_ENABLED=false` and
`JUSTONEAPI_ENABLED=true`, and provide a valid token. With the default
`LOCAL_CRAWLER_ENABLED=true`, the existing Playwright/account-pool path remains
available alongside JustOneAPI.

JustOneAPI sends its token as a query parameter. Never print the fully rendered
request URL, include it in task errors, or persist it in request audit metadata;
client logging and exception formatting must redact the token. The upstream OpenAPI
schema does not fully type endpoint `data` payloads. Validate the enabled endpoint
contracts with a real token in a controlled environment before production use.

These settings configure an alternative provider for finite tasks only. They do not
enable monitoring, scheduling, subscriptions, or recurring polling.

Runtime paths:

- `.venv/`
- `data/`
- `browser_data/`
- `exports/`
- `logs/`
- `database/*.db`
- `service/*.db`
- `*.log`

These are ignored by Git and should not be deployed as source.
