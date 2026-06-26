#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Entry point for the XHS 24/7 crawler web service.

Usage:
    uv run start_xhs_service.py
    uv run start_xhs_service.py --host 0.0.0.0 --port 8088 --headless
"""
import argparse
import os
import sys

# Force UTF-8 for Windows consoles
if sys.stdout and hasattr(sys.stdout, 'buffer') and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer') and sys.stderr.encoding.lower() != 'utf-8':
    import io
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Ensure project root is importable
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    return int(raw)


def parse_args():
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = _int_env("PORT", 8088)
    p = argparse.ArgumentParser(description="XHS Crawler Web Service")
    p.add_argument("--host", default=None, help=f"Bind host (default: {default_host})")
    p.add_argument("--port", type=int, default=None, help=f"Bind port (default: {default_port})")
    p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    p.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    host = args.host or os.environ.get("HOST", "0.0.0.0")
    port = args.port or _int_env("PORT", 8088)
    reload = args.reload or _bool_env("RELOAD", False)

    # Set browser headless mode before importing the FastAPI application.
    if args.headless or _bool_env("HEADLESS", False):
        os.environ["HEADLESS"] = "true"
        os.environ["CDP_CONNECT_EXISTING"] = "false"

    print(f"[XHS Service] Starting on http://{host}:{port}")
    print("[XHS Service] Web UI: http://127.0.0.1:" + str(port))

    uvicorn.run(
        "service.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
