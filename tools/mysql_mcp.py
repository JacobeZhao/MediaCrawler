"""MySQL MCP Server — execute SQL, manage tables, import/export files, data cleaning."""

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import pymysql
import pymysql.cursors
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "MySQL",
    instructions=(
        "MySQL database operations. "
        "Tools: execute_sql (any SQL), list_databases, list_tables, describe_table, "
        "import_file (JSONL/CSV/TSV/JSON/Excel → table), export_to_file (query → file), "
        "clean_table (dedup / drop nulls / trim strings). "
        "Always specify database= when targeting a specific schema."
    ),
)

_HOST = os.environ.get("MYSQL_HOST", "")
_PORT = int(os.environ.get("MYSQL_PORT", 3306))
_USER = os.environ.get("MYSQL_USER", "")
_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
_DEFAULT_DB = os.environ.get("MYSQL_DATABASE", "")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect(database: str = "") -> pymysql.connections.Connection:
    return pymysql.connect(
        host=_HOST,
        port=_PORT,
        user=_USER,
        password=_PASSWORD,
        database=database or _DEFAULT_DB or "",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


def _is_read_query(sql: str) -> bool:
    first = sql.strip().upper().split()[0] if sql.strip() else ""
    return first in {"SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN", "WITH"}


def _sanitize_col(name: str) -> str:
    safe = re.sub(r"[^\w]", "_", str(name).strip())
    if not safe or safe[0].isdigit():
        safe = "col_" + safe
    return safe.lower()


def _infer_mysql_type(values: list) -> str:
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    if not non_null:
        return "TEXT"
    sample = non_null[:200]
    try:
        for v in sample:
            int(str(v))
        max_val = max(abs(int(str(v))) for v in sample)
        return "BIGINT" if max_val > 2_147_483_647 else "INT"
    except (ValueError, TypeError):
        pass
    try:
        for v in sample:
            float(str(v))
        return "DOUBLE"
    except (ValueError, TypeError):
        pass
    max_len = max(len(str(v)) for v in sample)
    if max_len <= 512:
        return "VARCHAR(512)"
    if max_len <= 2048:
        return "VARCHAR(2048)"
    return "LONGTEXT"


def _batch_insert(conn, table: str, rows: list, batch_size: int = 500) -> int:
    if not rows:
        return 0
    cols = list(rows[0].keys())
    col_clause = ", ".join(f"`{c}`" for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    sql = f"INSERT IGNORE INTO `{table}` ({col_clause}) VALUES ({placeholders})"
    total = 0
    with conn.cursor() as cur:
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            values = [
                tuple(
                    json.dumps(r.get(c), ensure_ascii=False) if isinstance(r.get(c), (dict, list))
                    else (None if r.get(c) is None else str(r.get(c)))
                    for c in cols
                )
                for r in batch
            ]
            cur.executemany(sql, values)
            total += cur.rowcount
    conn.commit()
    return total


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def execute_sql(
    sql: str,
    database: str = "",
    params: str = "",
) -> str:
    """Execute any SQL statement: SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, DROP, SHOW, etc.

    Args:
        sql: SQL statement (supports %s placeholders)
        database: target database/schema name (uses env default if empty)
        params: optional JSON array of positional params, e.g. '[1, "foo"]'

    Returns rows for SELECT/SHOW, or affected_rows for DML/DDL.
    Supports multiple statements separated by semicolons for DDL batches.
    """
    parsed_params = json.loads(params) if params.strip() else None
    try:
        conn = _connect(database)
        try:
            results = []
            statements = [s.strip() for s in sql.split(";") if s.strip()]
            with conn.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt, parsed_params)
                    if _is_read_query(stmt):
                        rows = cur.fetchall()
                        results.append({"sql": stmt[:80], "rows": rows, "count": len(rows)})
                    else:
                        conn.commit()
                        results.append({
                            "sql": stmt[:80],
                            "affected_rows": cur.rowcount,
                            "last_insert_id": cur.lastrowid,
                        })
            return json.dumps(results if len(results) > 1 else results[0], ensure_ascii=False, default=str, indent=2)
        finally:
            conn.close()
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def list_databases() -> str:
    """List all databases/schemas on the MySQL server."""
    try:
        conn = _connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW DATABASES")
                rows = cur.fetchall()
            dbs = [list(r.values())[0] for r in rows]
            return json.dumps({"databases": dbs}, ensure_ascii=False)
        finally:
            conn.close()
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def list_tables(database: str = "") -> str:
    """List all tables in a database.

    Args:
        database: database name (uses env default if empty)
    """
    try:
        conn = _connect(database)
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES")
                rows = cur.fetchall()
            tables = [list(r.values())[0] for r in rows]
            return json.dumps({"database": database or _DEFAULT_DB, "tables": tables}, ensure_ascii=False)
        finally:
            conn.close()
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def describe_table(table: str, database: str = "") -> str:
    """Show column schema for a table (name, type, nullable, key, default).

    Args:
        table: table name
        database: database name (uses env default if empty)
    """
    try:
        conn = _connect(database)
        try:
            with conn.cursor() as cur:
                cur.execute(f"DESCRIBE `{table}`")
                cols = cur.fetchall()
                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM information_schema.TABLES "
                    "WHERE table_schema = DATABASE() AND table_name = %s",
                    (table,),
                )
                row_count_info = cur.fetchone()
            return json.dumps(
                {"table": table, "columns": cols, "approx_rows": row_count_info},
                ensure_ascii=False, default=str, indent=2,
            )
        finally:
            conn.close()
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def import_file(
    file_path: str,
    table: str,
    database: str = "",
    create_if_not_exists: bool = True,
    encoding: str = "utf-8",
    csv_delimiter: str = ",",
    flatten_nested: bool = True,
) -> str:
    """Import a data file into a MySQL table. Supports JSONL, JSON, CSV, TSV, Excel.

    Args:
        file_path: absolute path to the source file
        table: target table name
        database: target database (uses env default if empty)
        create_if_not_exists: auto-create table by inferring schema from data (default True)
        encoding: file text encoding (default utf-8)
        csv_delimiter: CSV column delimiter (default ','; use '\\t' for TSV)
        flatten_nested: serialize nested dicts/lists as JSON strings (default True)

    Notes:
        - Duplicate rows with same unique key are silently ignored (INSERT IGNORE)
        - Auto-created tables include an _id BIGINT AUTO_INCREMENT primary key
        - Column names are sanitized (spaces/special chars → underscore, lowercased)
    """
    path = Path(file_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    ext = path.suffix.lower()
    rows: list = []

    try:
        if ext == ".jsonl":
            with open(path, "r", encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        elif ext == ".json":
            with open(path, "r", encoding=encoding) as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else [data]
        elif ext in (".csv", ".txt"):
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f, delimiter=csv_delimiter)
                rows = [dict(r) for r in reader]
        elif ext == ".tsv":
            with open(path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                rows = [dict(r) for r in reader]
        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                ws = wb.active
                headers = [str(cell.value) if cell.value is not None else f"col_{i}" for i, cell in enumerate(next(ws.iter_rows(max_row=1)))]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    rows.append({h: v for h, v in zip(headers, row)})
                wb.close()
            except ImportError:
                return json.dumps({"error": "openpyxl not installed. Run: pip install openpyxl"})
        else:
            return json.dumps({"error": f"Unsupported file type '{ext}'. Supported: .jsonl .json .csv .tsv .txt .xlsx .xls"})
    except Exception as e:
        return json.dumps({"error": f"Failed to read file: {e}"})

    if not rows:
        return json.dumps({"error": "File is empty or has no data rows."})

    flat_rows = []
    for row in rows:
        flat = {}
        for k, v in row.items():
            col = _sanitize_col(k)
            if flatten_nested and isinstance(v, (dict, list)):
                flat[col] = json.dumps(v, ensure_ascii=False)
            else:
                flat[col] = v
        flat_rows.append(flat)
    rows = flat_rows

    try:
        conn = _connect(database)
    except Exception as e:
        return json.dumps({"error": f"DB connection failed: {e}"})

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM information_schema.TABLES "
                "WHERE table_schema = DATABASE() AND table_name = %s",
                (table,),
            )
            table_exists = cur.fetchone()["cnt"] > 0

        if not table_exists:
            if not create_if_not_exists:
                return json.dumps({"error": f"Table '{table}' does not exist. Pass create_if_not_exists=true to auto-create."})
            all_cols = list(rows[0].keys())
            col_defs = []
            for col in all_cols:
                vals = [r.get(col) for r in rows]
                col_defs.append(f"  `{col}` {_infer_mysql_type(vals)}")
            create_sql = (
                f"CREATE TABLE IF NOT EXISTS `{table}` (\n"
                f"  `_id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,\n"
                + ",\n".join(col_defs)
                + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            )
            with conn.cursor() as cur:
                cur.execute(create_sql)
            conn.commit()

        inserted = _batch_insert(conn, table, rows)
        return json.dumps(
            {
                "status": "ok",
                "file": path.name,
                "table": table,
                "database": database or _DEFAULT_DB,
                "rows_read": len(rows),
                "rows_inserted": inserted,
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"Import failed: {e}"})
    finally:
        conn.close()


@mcp.tool()
def export_to_file(
    sql: str,
    output_path: str,
    fmt: str = "csv",
    database: str = "",
    encoding: str = "utf-8",
) -> str:
    """Execute a SELECT query and save results to a file.

    Args:
        sql: SELECT statement
        output_path: absolute path for the output file (parent dirs auto-created)
        fmt: output format — csv | jsonl | json (default csv)
        database: database name (uses env default if empty)
        encoding: output encoding (default utf-8)
    """
    try:
        conn = _connect(database)
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        return json.dumps({"error": f"Query failed: {e}"})

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "jsonl":
            with open(path, "w", encoding=encoding) as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        elif fmt == "json":
            with open(path, "w", encoding=encoding) as f:
                json.dump(rows, f, ensure_ascii=False, default=str, indent=2)
        elif fmt == "csv":
            if not rows:
                path.write_text("", encoding=encoding)
            else:
                with open(path, "w", encoding=encoding, newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: (str(v) if v is not None else "") for k, v in row.items()})
        else:
            return json.dumps({"error": f"Unknown format '{fmt}'. Use: csv, jsonl, json"})

        return json.dumps(
            {"status": "ok", "output": str(path), "rows": len(rows), "format": fmt},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"Export failed: {e}"})


@mcp.tool()
def clean_table(
    table: str,
    database: str = "",
    dedup_columns: str = "",
    drop_null_columns: str = "",
    trim_string_columns: str = "",
    dry_run: bool = True,
) -> str:
    """Clean a table: remove duplicates, drop rows with nulls, trim whitespace.

    Args:
        table: table name to clean
        database: database name (uses env default if empty)
        dedup_columns: comma-separated columns to deduplicate on (keeps first occurrence by _id/pk)
        drop_null_columns: comma-separated columns — rows where ANY of these is NULL/empty are deleted
        trim_string_columns: comma-separated VARCHAR/TEXT columns to trim whitespace in-place
        dry_run: if True (default), only report what WOULD be changed without modifying data

    Returns a summary of actions taken (or planned if dry_run=True).
    """
    report = []
    try:
        conn = _connect(database)
    except Exception as e:
        return json.dumps({"error": f"Connection failed: {e}"})

    try:
        with conn.cursor() as cur:
            if dedup_columns.strip():
                cols = [c.strip() for c in dedup_columns.split(",") if c.strip()]
                col_clause = ", ".join(f"`{c}`" for c in cols)
                cur.execute(
                    f"SELECT COUNT(*) AS cnt FROM `{table}` t1 "
                    f"WHERE EXISTS ("
                    f"  SELECT 1 FROM `{table}` t2 "
                    f"  WHERE ({col_clause.replace('`', 't1.`')}) = ({col_clause.replace('`', 't2.`')}) "
                    f"  AND t2._id < t1._id"
                    f")"
                )
                dup_count = cur.fetchone()["cnt"]
                if not dry_run and dup_count > 0:
                    cur.execute(
                        f"DELETE t1 FROM `{table}` t1 "
                        f"INNER JOIN `{table}` t2 "
                        f"WHERE ({', '.join(f't1.`{c}`' for c in cols)}) = ({', '.join(f't2.`{c}`' for c in cols)}) "
                        f"AND t2._id < t1._id"
                    )
                    conn.commit()
                report.append({"action": "dedup", "columns": cols, "duplicate_rows": dup_count, "dry_run": dry_run})

            if drop_null_columns.strip():
                cols = [c.strip() for c in drop_null_columns.split(",") if c.strip()]
                null_conditions = " OR ".join(
                    f"(`{c}` IS NULL OR `{c}` = '')" for c in cols
                )
                cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table}` WHERE {null_conditions}")
                null_count = cur.fetchone()["cnt"]
                if not dry_run and null_count > 0:
                    cur.execute(f"DELETE FROM `{table}` WHERE {null_conditions}")
                    conn.commit()
                report.append({"action": "drop_nulls", "columns": cols, "rows_affected": null_count, "dry_run": dry_run})

            if trim_string_columns.strip():
                cols = [c.strip() for c in trim_string_columns.split(",") if c.strip()]
                for col in cols:
                    cur.execute(
                        f"SELECT COUNT(*) AS cnt FROM `{table}` "
                        f"WHERE `{col}` != TRIM(`{col}`) AND `{col}` IS NOT NULL"
                    )
                    trim_count = cur.fetchone()["cnt"]
                    if not dry_run and trim_count > 0:
                        cur.execute(f"UPDATE `{table}` SET `{col}` = TRIM(`{col}`) WHERE `{col}` IS NOT NULL")
                        conn.commit()
                    report.append({"action": "trim", "column": col, "rows_affected": trim_count, "dry_run": dry_run})

        return json.dumps({"table": table, "report": report}, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
