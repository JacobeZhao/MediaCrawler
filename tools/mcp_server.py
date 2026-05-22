import sys
import os
import json
from pathlib import Path
from typing import Optional

# tools/ 在项目根目录下一级，需要上移到项目根才能 import api.*
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP
from api.schemas.crawler import (
    CrawlerStartRequest,
    PlatformEnum,
    CrawlerTypeEnum,
    LoginTypeEnum,
    SaveDataOptionEnum,
)
from api.services.crawler_manager import crawler_manager as manager

mcp = FastMCP(
    "MediaCrawler",
    instructions=(
        "Social media crawler for XHS, Douyin, Kuaishou, Bilibili, Weibo, Tieba, Zhihu. "
        "Typical workflow: call search_content/get_content_by_ids/get_creator_content → "
        "poll get_crawl_status until status is 'idle' → call read_results to retrieve data. "
        "Cookies can be passed per-call or set via env vars (XHS_COOKIES, DY_COOKIES, etc.)."
    ),
)

DATA_DIR = PROJECT_ROOT / "data"

_VALID_PLATFORMS = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}


def _resolve_cookies(platform: str, cookies_param: str) -> tuple[str, str]:
    """Return (cookies, login_type). Prefers explicit param, falls back to env var."""
    cookies = cookies_param or os.environ.get(f"{platform.upper()}_COOKIES", "")
    return cookies, ("cookie" if cookies else "qrcode")


def _validate_platform(platform: str) -> Optional[str]:
    """Return error string if invalid, None if valid."""
    if platform not in _VALID_PLATFORMS:
        return f"Invalid platform '{platform}'. Valid: {', '.join(sorted(_VALID_PLATFORMS))}"
    return None


@mcp.tool()
async def search_content(
    platform: str,
    keywords: str,
    enable_comments: bool = True,
    enable_sub_comments: bool = False,
    max_notes_count: int = 15,
    max_comments_count: int = 10,
    save_option: str = "jsonl",
    save_data_path: str = "",
    cookies: str = "",
    headless: bool = True,
) -> str:
    """Start a keyword search crawl on a social media platform. Returns immediately (async).

    Args:
        platform: xhs | dy | ks | bili | wb | tieba | zhihu
        keywords: comma-separated keywords, e.g. "Python编程,副业"
        enable_comments: whether to also crawl first-level comments (default True)
        enable_sub_comments: whether to also crawl second-level/reply comments (default False)
        max_notes_count: max number of notes/posts to crawl (default 15)
        max_comments_count: max first-level comments per note (default 10; use 9999 for all)
        save_option: output format — jsonl | json | csv | excel | sqlite (default jsonl)
        save_data_path: custom directory to save results (default: project data/ folder)
        cookies: cookie string for cookie-based login (optional; also reads env XHS_COOKIES etc.)
        headless: run browser headless (default True; set False to see browser window)

    After calling this, use get_crawl_status() to monitor, then read_results() to get data.
    """
    if err := _validate_platform(platform):
        return err

    cookies_val, login_type = _resolve_cookies(platform, cookies)
    req = CrawlerStartRequest(
        platform=PlatformEnum(platform),
        login_type=LoginTypeEnum(login_type),
        crawler_type=CrawlerTypeEnum.SEARCH,
        keywords=keywords,
        enable_comments=enable_comments,
        enable_sub_comments=enable_sub_comments,
        max_notes_count=max_notes_count,
        max_comments_count=max_comments_count,
        save_option=SaveDataOptionEnum(save_option),
        save_data_path=save_data_path,
        cookies=cookies_val,
        headless=headless,
    )
    ok = await manager.start(req)
    if not ok:
        return (
            "Failed to start: a crawl is already running. "
            "Call stop_crawl() first or wait for it to finish (check get_crawl_status())."
        )
    return (
        f"Search crawl started — platform={platform}, keywords={keywords}, login={login_type}. "
        "Call get_crawl_status() to monitor progress, then read_results() when status is 'idle'."
    )


@mcp.tool()
async def get_content_by_ids(
    platform: str,
    ids: str,
    enable_comments: bool = True,
    save_option: str = "jsonl",
    cookies: str = "",
    headless: bool = True,
) -> str:
    """Crawl specific posts/videos by ID or URL. Returns immediately (async).

    Args:
        platform: xhs | dy | ks | bili | wb | tieba | zhihu
        ids: comma-separated post/video IDs or full URLs
        enable_comments: whether to also crawl comments (default True)
        save_option: output format — jsonl | json | csv | excel | sqlite (default jsonl)
        cookies: cookie string for login (optional)
        headless: run browser headless (default True)
    """
    if err := _validate_platform(platform):
        return err

    cookies_val, login_type = _resolve_cookies(platform, cookies)
    req = CrawlerStartRequest(
        platform=PlatformEnum(platform),
        login_type=LoginTypeEnum(login_type),
        crawler_type=CrawlerTypeEnum.DETAIL,
        specified_ids=ids,
        enable_comments=enable_comments,
        save_option=SaveDataOptionEnum(save_option),
        cookies=cookies_val,
        headless=headless,
    )
    ok = await manager.start(req)
    if not ok:
        return "Failed to start: a crawl is already running."
    return (
        f"Detail crawl started — platform={platform}, ids={ids}. "
        "Call get_crawl_status() to monitor, then read_results() when done."
    )


@mcp.tool()
async def get_creator_content(
    platform: str,
    creator_ids: str,
    enable_comments: bool = True,
    save_option: str = "jsonl",
    cookies: str = "",
    headless: bool = True,
) -> str:
    """Crawl a creator's posts on a social media platform. Returns immediately (async).

    Args:
        platform: xhs | dy | ks | bili | wb | tieba | zhihu
        creator_ids: comma-separated creator IDs or profile page URLs
        enable_comments: whether to also crawl comments (default True)
        save_option: output format — jsonl | json | csv | excel | sqlite (default jsonl)
        cookies: cookie string for login (optional)
        headless: run browser headless (default True)
    """
    if err := _validate_platform(platform):
        return err

    cookies_val, login_type = _resolve_cookies(platform, cookies)
    req = CrawlerStartRequest(
        platform=PlatformEnum(platform),
        login_type=LoginTypeEnum(login_type),
        crawler_type=CrawlerTypeEnum.CREATOR,
        creator_ids=creator_ids,
        enable_comments=enable_comments,
        save_option=SaveDataOptionEnum(save_option),
        cookies=cookies_val,
        headless=headless,
    )
    ok = await manager.start(req)
    if not ok:
        return "Failed to start: a crawl is already running."
    return (
        f"Creator crawl started — platform={platform}, creators={creator_ids}. "
        "Call get_crawl_status() to monitor, then read_results() when done."
    )


@mcp.tool()
async def get_crawl_status() -> str:
    """Get current crawl task status.

    Returns status (idle/running/stopping/error), platform, crawler_type,
    start time, and the 5 most recent log lines.
    """
    status = manager.get_status()
    status["recent_logs"] = [log.message for log in manager.logs[-5:]]
    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.tool()
async def stop_crawl() -> str:
    """Stop the currently running crawl task."""
    ok = await manager.stop()
    return "Crawl stopped." if ok else "No crawl is currently running."


@mcp.tool()
async def read_results(
    platform: str,
    data_type: str = "notes",
    limit: int = 20,
) -> str:
    """Read crawled data from the most recent output file.

    Args:
        platform: xhs | dy | ks | bili | wb | tieba | zhihu
        data_type: type of data to read — notes | comments | creators (default: notes)
        limit: max number of records to return (default: 20)

    Call this after get_crawl_status() returns status='idle'.
    """
    if err := _validate_platform(platform):
        return err

    if not DATA_DIR.exists():
        return "No data directory found. Run a crawl first."

    candidates = []
    for pattern in ("*.jsonl", "*.json"):
        for f in DATA_DIR.rglob(pattern):
            if platform.lower() in str(f).lower() and data_type.lower() in f.name.lower():
                candidates.append(f)

    if not candidates:
        all_files = [
            str(f.relative_to(DATA_DIR))
            for f in DATA_DIR.rglob("*")
            if f.is_file() and f.suffix.lower() in {".jsonl", ".json", ".csv", ".xlsx"}
        ]
        return (
            f"No '{data_type}' data found for platform '{platform}'. "
            f"Available files: {all_files or '(none — run a crawl first)'}"
        )

    target = max(candidates, key=lambda f: f.stat().st_mtime)
    records = []
    try:
        with open(target, "r", encoding="utf-8") as fh:
            if target.suffix == ".jsonl":
                for i, line in enumerate(fh):
                    if i >= limit:
                        break
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            else:
                data = json.load(fh)
                records = data[:limit] if isinstance(data, list) else [data]
    except Exception as e:
        return f"Error reading {target.name}: {e}"

    return json.dumps(
        {"file": str(target.relative_to(DATA_DIR)), "returned": len(records), "records": records},
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
async def list_result_files(platform: str = "") -> str:
    """List available crawled data files, sorted by modification time (newest first).

    Args:
        platform: optional filter, e.g. "xhs". Leave empty to list all platforms.
    """
    if not DATA_DIR.exists():
        return "No data directory found. Run a crawl first."

    files = []
    for f in sorted(
        (x for x in DATA_DIR.rglob("*") if x.is_file()),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    ):
        if f.suffix.lower() not in {".jsonl", ".json", ".csv", ".xlsx"}:
            continue
        if platform and platform.lower() not in str(f).lower():
            continue
        files.append({"path": str(f.relative_to(DATA_DIR)), "size_kb": round(f.stat().st_size / 1024, 1)})

    if not files:
        hint = f" for platform '{platform}'" if platform else ""
        return f"No data files found{hint}. Run a crawl first."
    return json.dumps({"files": files[:30]}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
