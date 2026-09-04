# Tools

`tools/` contains reusable maintenance utilities. Create one-off investigation
scripts in an OS temporary directory and remove them when the investigation ends.

## `create_search_tasks.py`

Creates keyword search tasks through the running FastAPI service.

Example:

```powershell
python tools/create_search_tasks.py keywords.txt --base-url http://127.0.0.1:8088 --max-notes 20 --max-comments 10000
```

Accepted input formats:

- plain text: one keyword per line
- JSON list, or object with `keywords`
- CSV with one of these columns: `月度`, `月度关键词`, `keyword`, `关键词`, `搜索词`

This tool writes tasks to the service API.

## `export_note_comments_md.py`

Exports one saved note and its comment/reply tree from the running service to a
Markdown file.

```powershell
python tools/export_note_comments_md.py --api-base http://127.0.0.1:8088 --note-id NOTE_ID --output exports/note.md
```

## `sync_comments_to_dwd.py`

Synchronizes XHS ODS comments into the MySQL DWD comment-thread table.

Example:

```powershell
python tools/sync_comments_to_dwd.py --keywords 米粉推荐婴儿,核桃油
```

Requirements:

- `.env` must define `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, and `MYSQL_PASSWORD`.
- Target database is `ai_platform`.

This tool writes to MySQL. Review the target keywords and period mapping before
running it against production data.

## Shared Utilities

- `verify.py`: standard-library local/CI verification orchestrator; see `docs/testing.md`.
- `crawler_util.py`: browser/crawler helper functions used by the XHS flow.
- `httpx_util.py`: configured `httpx.AsyncClient` factory.
- `time_util.py`: timestamp and date conversion helpers.
- `utils.py`: logging setup and small CLI helpers.
