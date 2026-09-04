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

`config/settings.py` is the canonical source for application setting names,
types, and defaults. `.env.example` is the exhaustive application-setting
inventory and groups the controls by responsibility:

- Server and runtime selection: `HOST`, `PORT`, `RELOAD`, `SAVE_DATA_OPTION`,
  `XHS_INTERNATIONAL`, `HEADLESS`, `CDP_CONNECT_EXISTING`, and
  `LOCAL_CRAWLER_ENABLED`.
- SQLite and lock paths: `SQLITE_DB_PATH`, `SERVICE_DB_PATH`, and
  `RUNTIME_LOCK_PATH`.
- Crawl pacing: `CRAWLER_MIN_SLEEP_SEC`, `CRAWLER_MAX_SLEEP_SEC`,
  `CRAWLER_GLOBAL_MIN_INTERVAL_SEC`, `CRAWLER_ACCOUNT_MIN_INTERVAL_SEC`,
  `CRAWLER_SEARCH_MIN_INTERVAL_SEC`, `CRAWLER_DETAIL_MIN_INTERVAL_SEC`,
  `CRAWLER_COMMENT_MIN_INTERVAL_SEC`, `CRAWLER_CREATOR_MIN_INTERVAL_SEC`,
  `CRAWLER_TASK_START_JITTER_MIN_SEC`, and
  `CRAWLER_TASK_START_JITTER_MAX_SEC`.
- Crawl workload and risk bounds: `CRAWLER_ACCOUNT_REQUEST_BUDGET`,
  `CRAWLER_ACCOUNT_BUDGET_REST_MIN_SEC`,
  `CRAWLER_ACCOUNT_BUDGET_REST_MAX_SEC`, `CRAWLER_RISK_BACKOFF_SEC`,
  `CRAWLER_TASK_MAX_NOTES_PER_TASK`, `CRAWLER_TASK_MAX_COMMENTS_PER_NOTE`,
  `CRAWLER_MAX_NOTES_COUNT`, and `CRAWLER_MAX_COMMENTS_COUNT_SINGLE_NOTE`.
- Account, task, circuit, and queue controls: `ACCOUNT_COOLDOWN_BASE_SEC`,
  `ACCOUNT_COOLDOWN_MAX_SEC`, `ACCOUNT_HEALTH_CHECK_INTERVAL_SEC`,
  `TASK_PAUSE_ON_ACCOUNT_ERROR`, `CIRCUIT_WINDOW_SEC`, `CIRCUIT_PAUSE_SEC`,
  `CIRCUIT_ERROR_THRESHOLD`, `TASK_MAX_ACCOUNT_SWITCHES`,
  `TASK_MAX_RUNTIME_SEC`, `MAX_QUEUE_SIZE`, and `MAX_BATCH_TASKS`.
- JustOneAPI: `JUSTONEAPI_ENABLED`, `JUSTONEAPI_TOKEN`,
  `JUSTONEAPI_BASE_URL`, `JUSTONEAPI_TIMEOUT_SEC`,
  `JUSTONEAPI_MAX_RETRIES`, `JUSTONEAPI_RETRY_BASE_SEC`, and
  `JUSTONEAPI_MAX_REQUESTS_PER_TASK`.

The sample is configured for the normal unattended service mode, so it
intentionally sets `HEADLESS=true` and `CDP_CONNECT_EXISTING=false`; the code
defaults remain `false` and `true` respectively. Path settings are commented
examples so a checkout can retain the portable defaults from
`config/settings.py`.

`XHS_COOKIES` is retained as a blank historical placeholder; no active
`Settings` field or tracked runtime consumer reads it. `JUSTONEAPI_TOKEN` and
all other sensitive placeholders must remain blank in the tracked sample.

`XHS_ENV_FILE` is a parent-process selector, not an application setting and not
a valid entry inside an environment file. Supervisor-only inputs such as
`XHS_PYTHON`, `XHS_LOG_DIR`, and `XHS_RESTART_DELAY_SECONDS` are owned and
documented by `ops/README.md`.

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
