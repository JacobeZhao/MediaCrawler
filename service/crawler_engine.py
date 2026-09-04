# -*- coding: utf-8 -*-
"""
Persistent XHS crawler engine 鈥?keeps a single browser session alive for 24/7 service.
"""
import asyncio
import random
import os
import sys
from typing import Any, Callable, Dict, List, Optional

# Ensure project root is importable
_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from playwright.async_api import BrowserContext, Page, async_playwright
from tenacity import RetryError

import aiosqlite
import config
from config.db_config import SQLITE_DB_PATH
from database.db_session import create_tables
from media_platform.xhs.client import (
    XiaoHongShuClient,
    XHSAuthError,
    XHSCaptchaError,
    XHSPermissionError,
    XHSRateLimitError,
)
from media_platform.xhs.field import SearchSortType
from media_platform.xhs.help import get_search_id, parse_creator_info_from_url, parse_note_info_from_note_url
from media_platform.xhs.login import XiaoHongShuLogin
from store import xhs as xhs_store
from tools.crawler_util import convert_browser_context_cookies, convert_cookies
from tools.redaction import redact_sensitive_text
from tools.utils import logger
from var import crawler_type_var, source_keyword_var
from .image_downloader import download_note_images
from .executors.base import ExecutorLeaseLost
from .proxy_config import build_proxy_url
from .rate_limiter import rate_limiter


_IMAGE_DIR = os.path.join(_PROJECT_ROOT, "data", "xhs", "images")


class CaptchaException(Exception):
    """Raised when an XHS account triggers CAPTCHA / risk-control."""
    pass


def _is_captcha_error(exc: Exception) -> bool:
    root_exc = _unwrap_retry_error(exc)
    if isinstance(root_exc, XHSCaptchaError):
        return True
    msg = str(root_exc).lower()
    return "captcha appeared" in msg or "website-login/captcha" in msg



def _is_recoverable_account_error(exc: Exception) -> bool:
    """True -> switch account instead of failing the task immediately."""
    root_exc = _unwrap_retry_error(exc)
    if isinstance(
        root_exc,
        (XHSAuthError, XHSCaptchaError, XHSPermissionError, XHSRateLimitError),
    ):
        return True
    if _is_captcha_error(root_exc):
        return True
    msg = str(root_exc).lower()
    return (
        "ipblockerror" in msg
        or "ip_error" in msg
        or "rate limit" in msg
        or "429" in msg
        or "403" in msg
        or "401" in msg
        or "unauthorized" in msg
        or "login" in msg
        or "登录" in msg
        or "登陆" in msg
        or "session" in msg
        or "cookie" in msg
        or "account blocked" in msg
        or "forbidden" in msg
        or "block" in type(exc).__name__.lower()
    )


def _unwrap_retry_error(exc: Exception) -> Exception:
    if isinstance(exc, RetryError):
        try:
            last_exc = exc.last_attempt.exception()
            if last_exc:
                return last_exc
        except Exception:
            pass
    return exc

class XHSCrawlerEngine:
    """Persistent browser + XHS API client, processes tasks sequentially."""

    def __init__(
        self,
        account_id: Optional[int] = None,
        user_data_dir: Optional[str] = None,
        proxy_config: Optional[Dict] = None,
    ):
        self._playwright = None
        self._browser_context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._xhs_client: Optional[XiaoHongShuClient] = None
        self._lock = asyncio.Lock()
        self.status = "stopped"       # stopped / initializing / need_login / ready / crawling / error / captcha
        self.message = ""
        self.account_id = account_id  # None = default account
        self._user_data_dir = user_data_dir  # None = use default path
        self._proxy_config = proxy_config
        self._proxy_url = build_proxy_url(proxy_config)
        self._index_url = "https://www.rednote.com" if config.XHS_INTERNATIONAL else "https://www.xiaohongshu.com"
        self._user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        )

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def start(self):
        """Start browser and attempt to reuse saved login state."""
        self.status = "initializing"
        self.message = "Starting browser..."
        try:
            self._playwright = await async_playwright().start()
            await self._launch_browser()
            await self._refresh_client()

            if not await self._xhs_client.pong():
                self.status = "need_login"
                self.message = "Not logged in. Set a cookie or scan the QR code in the web UI."
            else:
                self.status = "ready"
                self.message = "Ready"
        except Exception as exc:
            self.status = "error"
            safe_error = redact_sensitive_text(exc)
            self.message = f"Startup failed: {safe_error}"
            logger.error(f"[XHSCrawlerEngine.start] {safe_error}")

    async def stop(self):
        """Gracefully stop browser."""
        if self._browser_context:
            try:
                await self._browser_context.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
        self._browser_context = None
        self._page = None
        self._xhs_client = None
        self._playwright = None
        self.status = "stopped"
        self.message = ""

    async def set_cookie(self, cookie_str: str) -> bool:
        """Set cookie directly into the XHS client and verify login."""
        if not self._browser_context:
            return False
        try:
            # Parse cookie string into dict
            cookie_dict: Dict[str, str] = {}
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    name, _, value = part.partition("=")
                    cookie_dict[name.strip()] = value.strip()

            if not cookie_dict:
                self.message = "Invalid cookie format"
                return False

            # Set cookies in browser context as well (for page navigation)
            domain = ".rednote.com" if config.XHS_INTERNATIONAL else ".xiaohongshu.com"
            cookies_to_add = [
                {"name": k, "value": v, "domain": domain, "path": "/"}
                for k, v in cookie_dict.items()
            ]
            try:
                await self._browser_context.clear_cookies()
                await self._browser_context.add_cookies(cookies_to_add)
            except Exception:
                pass

            # Directly update the XHS client headers 鈥?bypass browser readback
            await self._refresh_client()
            # Override cookie in client headers with the provided string
            self._xhs_client.headers["Cookie"] = cookie_str
            self._xhs_client.cookie_dict = cookie_dict

            if await self._xhs_client.pong():
                self.status = "ready"
                self.message = "Cookie login succeeded"
                return True
            self.message = "Cookie is invalid; please refresh it"
            return False
        except Exception as exc:
            self.message = f"Failed to set cookie: {redact_sensitive_text(exc)}"
            return False

    async def trigger_qrcode_login(self) -> bool:
        """Trigger QR code login flow (opens the browser window)."""
        if not self._browser_context or not self._page:
            return False
        try:
            login_obj = XiaoHongShuLogin(
                login_type="qrcode",
                login_phone="",
                browser_context=self._browser_context,
                context_page=self._page,
                cookie_str="",
            )
            await login_obj.begin()
            await self._refresh_client()
            if await self._xhs_client.pong():
                self.status = "ready"
                self.message = "QR login succeeded"
                return True
            return False
        except Exception as exc:
            self.message = f"QR login failed: {redact_sensitive_text(exc)}"
            return False

    def get_status(self) -> Dict:
        return {"status": self.status, "message": self.message}

    async def probe_login(self) -> Dict[str, Any]:
        """Return a soft login probe without exposing the underlying XHS client."""
        cookie = ""
        has_login_cookie = False
        ok = False
        error = None
        try:
            if not self._xhs_client:
                return {
                    "ok": False,
                    "has_login_cookie": False,
                    "error": "XHS client is not initialized",
                }
            cookie = self._xhs_client.headers.get("Cookie", "")
            has_login_cookie = "web_session=" in cookie or "a1=" in cookie
            self_info = await self._xhs_client.query_self()
            ok = bool(self_info and self_info.get("data", {}).get("result", {}).get("success"))
            if not ok and self_info:
                error = redact_sensitive_text(
                    self_info.get("msg") or "XHS login probe returned an unsuccessful result"
                )
        except Exception as exc:
            error = redact_sensitive_text(exc)
        return {"ok": ok, "has_login_cookie": has_login_cookie, "error": error}

    # ------------------------------------------------------------------ #
    #  Crawl tasks                                                         #
    # ------------------------------------------------------------------ #

    async def search_keyword(
        self,
        keyword: str,
        max_notes: int = 20,
        enable_comments: bool = True,
        enable_images: bool = False,
        max_comments: int = 20,
        progress_cb: Optional[Callable[[str], Any]] = None,
        force: bool = False,
        sort_type: str = "popularity_descending",
        days_limit: int = 0,
    ) -> Dict:
        """Keyword search: crawl notes and optional comments."""
        async with self._lock:
            self.status = "crawling"
            self.message = f"Searching keyword: {keyword}"
            try:
                result = await self._do_search(
                    keyword, max_notes, enable_comments, enable_images, max_comments, progress_cb, force, sort_type, days_limit
                )
                self.status = "ready"
                self.message = "Ready"
                return result
            except CaptchaException as exc:
                self.status = "captcha"
                self.message = "Account requires captcha; switch account"
                logger.warning(
                    f"[XHSCrawlerEngine.search_keyword] CAPTCHA: {redact_sensitive_text(exc)}"
                )
                raise
            except ExecutorLeaseLost:
                self.status = "ready"
                self.message = "Ready"
                raise
            except Exception as exc:
                self.status = "error"
                safe_error = redact_sensitive_text(exc)
                self.message = f"Search failed: {safe_error}"
                logger.error(f"[XHSCrawlerEngine.search_keyword] {safe_error}")
                raise

    async def crawl_creator(
        self,
        creator_input: str,
        max_notes: int = 20,
        enable_images: bool = True,
        enable_comments: bool = False,
        max_comments: int = 20,
        progress_cb: Optional[Callable[[str], Any]] = None,
        force: bool = False,
    ) -> Dict:
        """Crawl creator homepage: latest N notes + optional images."""
        async with self._lock:
            self.status = "crawling"
            self.message = f"Crawling creator: {creator_input[:30]}"
            try:
                result = await self._do_crawl_creator(
                    creator_input, max_notes, enable_images, enable_comments, max_comments, progress_cb, force
                )
                self.status = "ready"
                self.message = "Ready"
                return result
            except CaptchaException as exc:
                self.status = "captcha"
                self.message = "Account requires captcha; switch account"
                logger.warning(
                    f"[XHSCrawlerEngine.crawl_creator] CAPTCHA: {redact_sensitive_text(exc)}"
                )
                raise
            except ExecutorLeaseLost:
                self.status = "ready"
                self.message = "Ready"
                raise
            except Exception as exc:
                self.status = "error"
                safe_error = redact_sensitive_text(exc)
                self.message = f"Crawl failed: {safe_error}"
                logger.error(f"[XHSCrawlerEngine.crawl_creator] {safe_error}")
                raise

    async def crawl_notes(
        self,
        note_items: List[Dict],  # [{"note_input": url_or_id, "d_level": "D2", "quality": "浼樼瓑鐢?}, ...]
        max_comments: int = 0,
        include_replies: bool = False,
        progress_cb: Optional[Callable[[str], Any]] = None,
    ) -> Dict:
        """Crawl specific notes by URL or ID."""
        async with self._lock:
            self.status = "crawling"
            self.message = f"Crawling {len(note_items)} notes"
            try:
                result = await self._do_crawl_notes(
                    note_items,
                    max_comments,
                    include_replies,
                    progress_cb,
                )
                self.status = "ready"
                self.message = "Ready"
                return result
            except CaptchaException as exc:
                self.status = "captcha"
                self.message = "Account requires captcha; switch account"
                logger.warning(
                    f"[XHSCrawlerEngine.crawl_notes] CAPTCHA: {redact_sensitive_text(exc)}"
                )
                raise
            except ExecutorLeaseLost:
                self.status = "ready"
                self.message = "Ready"
                raise
            except Exception as exc:
                self.status = "error"
                safe_error = redact_sensitive_text(exc)
                self.message = f"Crawl failed: {safe_error}"
                logger.error(f"[XHSCrawlerEngine.crawl_notes] {safe_error}")
                raise

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _launch_browser(self):
        user_data_dir = self._user_data_dir or os.path.join(_PROJECT_ROOT, "browser_data", "xhs_user_data_dir")
        os.makedirs(user_data_dir, exist_ok=True)
        chromium = self._playwright.chromium
        launch_kwargs = {
            "user_data_dir": user_data_dir,
            "accept_downloads": True,
            "headless": config.HEADLESS,
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": self._user_agent,
        }
        if self._proxy_config:
            launch_kwargs["proxy"] = self._proxy_config
        self._browser_context = await chromium.launch_persistent_context(**launch_kwargs)
        stealth_path = os.path.join(_PROJECT_ROOT, "libs", "stealth.min.js")
        if os.path.exists(stealth_path):
            await self._browser_context.add_init_script(path=stealth_path)

        pages = self._browser_context.pages
        self._page = pages[0] if pages else await self._browser_context.new_page()
        await self._page.goto(self._index_url, wait_until="domcontentloaded")

    async def _refresh_client(self):
        """Re-build XiaoHongShuClient using current browser cookies."""
        cookie_str, cookie_dict = await convert_browser_context_cookies(
            self._browser_context,
            urls=[self._index_url],
        )
        self._xhs_client = XiaoHongShuClient(
            headers={
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json;charset=UTF-8",
                "origin": self._index_url,
                "pragma": "no-cache",
                "referer": f"{self._index_url}/",
                "sec-ch-ua": '"Chromium";v="126", "Google Chrome";v="126", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": self._user_agent,
                "Cookie": cookie_str,
            },
            playwright_page=self._page,
            cookie_dict=cookie_dict,
            proxy_url=self._proxy_url,
        )

    async def _before_request(self, endpoint: str):
        await rate_limiter.acquire(self.account_id, endpoint)

    async def _do_search(
        self,
        keyword: str,
        max_notes: int,
        enable_comments: bool,
        enable_images: bool,
        max_comments: int,
        progress_cb,
        force: bool = False,
        sort_type: str = "popularity_descending",
        days_limit: int = 0,
    ) -> Dict:
        # Ensure SQLite tables exist
        config.SAVE_DATA_OPTION = "sqlite"
        await create_tables("sqlite")

        crawler_type_var.set("search")
        source_keyword_var.set(keyword)

        xhs_page_limit = 20

        search_id = get_search_id()
        page = 1
        total_notes = 0
        total_comments = 0
        note_ids: List[str] = []
        xsec_tokens: List[str] = []

        # Load already-saved note_ids to skip on resume (skip when force=True for re-crawl)
        if force:
            seen_ids: set = set()
            initial_count = 0
            effective_target = max_notes
        else:
            seen_ids: set = await _load_existing_note_ids("source_keyword", keyword)
            initial_count = len(seen_ids)
            # Target: total notes in DB (existing + new) reaches max_notes
            # Ensure at least one page is always fetched
            effective_target = max(max_notes - initial_count, xhs_page_limit)

        import time as _time
        cutoff_ms = (int(_time.time()) - days_limit * 86400) * 1000 if days_limit > 0 else 0

        while total_notes < effective_target:
            logger.info(f"[search] keyword={keyword} page={page}")
            try:
                await self._before_request("search")
                notes_res = await self._xhs_client.get_note_by_keyword(
                    keyword=keyword,
                    search_id=search_id,
                    page=page,
                    sort=SearchSortType(sort_type),
                )
            except Exception as exc:
                root_exc = _unwrap_retry_error(exc)
                logger.error(
                    f"[search] get_note_by_keyword error page={page}: "
                    f"{type(root_exc).__name__}: {redact_sensitive_text(root_exc)}"
                )
                if _is_captcha_error(root_exc):
                    raise CaptchaException(str(root_exc)) from root_exc
                raise RuntimeError(
                    f"Search API failed for keyword={keyword!r} page={page}: "
                    f"{type(root_exc).__name__}: {root_exc}"
                ) from root_exc

            if not notes_res:
                break

            items = [
                i for i in notes_res.get("items", [])
                if i.get("model_type") not in ("rec_query", "hot_query")
            ]

            # Skip notes already saved (deduplication for resume)
            new_items = [i for i in items if i.get("id") not in seen_ids]
            skipped = len(items) - len(new_items)
            if skipped:
                logger.info(f"[search] page={page} skipped {skipped} existing notes")

            sem = asyncio.Semaphore(1)
            tasks = [
                self._fetch_note_detail(
                    i.get("id"), i.get("xsec_source", "pc_search"), i.get("xsec_token", ""), sem
                )
                for i in new_items
            ]
            details = await asyncio.gather(*tasks)

            page_comment_targets = []
            for nd in details:
                if nd:
                    if cutoff_ms > 0:
                        note_time = nd.get("time", 0)
                        if note_time and int(note_time) < cutoff_ms:
                            logger.info(f"[search] skip old note {nd.get('note_id')} time={note_time}")
                            continue
                    await xhs_store.update_xhs_note(nd)
                    nid = nd.get("note_id", "")
                    await download_note_images(nid, nd.get("image_list", []), _IMAGE_DIR)
                    seen_ids.add(nid)
                    note_ids.append(nid)
                    token = nd.get("xsec_token", "")
                    xsec_tokens.append(token)
                    page_comment_targets.append((nid, token))
                    total_notes += 1
                    if progress_cb:
                        await _safe_call(
                            progress_cb,
                            f"Collected {total_notes} notes, {total_comments} comments",
                            total_notes,
                            total_comments,
                        )

            if enable_comments:
                for nid, tok in page_comment_targets:
                    if not nid:
                        continue

                    async def _comment_progress(message: str, note_comment_count: int = 0):
                        if progress_cb:
                            await _safe_call(
                                progress_cb,
                                message,
                                total_notes,
                                total_comments + note_comment_count,
                            )

                    cnt = await self._fetch_and_store_comments(
                        nid,
                        tok,
                        max_comments,
                        progress_cb=_comment_progress,
                    )
                    total_comments += cnt
                    if progress_cb:
                        await _safe_call(
                            progress_cb,
                            f"Collected {total_notes} notes, {total_comments} comments",
                            total_notes,
                            total_comments,
                        )

            page += 1
            if progress_cb:
                await _safe_call(
                    progress_cb,
                    f"Collected {total_notes} notes, {total_comments} comments",
                    total_notes,
                    total_comments,
                )
            await asyncio.sleep(random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC) * 2)
            if not notes_res.get("has_more", False):
                break

        # Query total comments in DB for this keyword
        total_comments_in_db = 0
        if os.path.exists(SQLITE_DB_PATH):
            async with aiosqlite.connect(SQLITE_DB_PATH) as _db:
                cur = await _db.execute(
                    "SELECT COUNT(*) FROM xhs_note_comment WHERE note_id IN "
                    "(SELECT note_id FROM xhs_note WHERE source_keyword=?)",
                    (keyword,),
                )
                row = await cur.fetchone()
                total_comments_in_db = row[0] if row else 0

        return {
            "notes_count": total_notes,
            "comments_count": total_comments,
            "total_notes_in_db": len(seen_ids),
            "total_comments_in_db": total_comments_in_db,
        }

    async def _do_crawl_creator(
        self,
        creator_input: str,
        max_notes: int,
        enable_images: bool,
        enable_comments: bool,
        max_comments: int,
        progress_cb,
        force: bool = False,
    ) -> Dict:
        config.SAVE_DATA_OPTION = "sqlite"
        config.CRAWLER_MAX_NOTES_COUNT = max_notes
        await create_tables("sqlite")

        crawler_type_var.set("creator")

        creator_info = parse_creator_info_from_url(creator_input)
        user_id = creator_info.user_id
        source_keyword_var.set(user_id)

        # Fetch and store creator profile
        try:
            creator_data = await self._xhs_client.get_creator_info(
                user_id=user_id,
                xsec_token=creator_info.xsec_token,
                xsec_source=creator_info.xsec_source,
            )
            if creator_data:
                await xhs_store.save_creator(user_id, creator=creator_data)
        except Exception as exc:
            logger.warning(
                f"[crawl_creator] get_creator_info error: {redact_sensitive_text(exc)}"
            )

        total_notes = 0
        total_comments = 0
        collected_note_ids: List[str] = []
        collected_xsec_tokens: List[str] = []

        # Load already-saved note_ids to skip on resume (skip when force=True for re-crawl)
        if force:
            seen_ids: set = set()
        else:
            seen_ids: set = await _load_existing_note_ids("user_id", user_id)

        async def _on_notes_batch(note_list: List[Dict]):
            nonlocal total_notes
            new_notes = [n for n in note_list if n.get("note_id") not in seen_ids]
            skipped = len(note_list) - len(new_notes)
            if skipped:
                logger.info(f"[creator] skipped {skipped} existing notes")
            sem = asyncio.Semaphore(1)
            tasks = [
                self._fetch_note_detail(
                    n.get("note_id"), n.get("xsec_source", "pc_user_feed"), n.get("xsec_token", ""), sem
                )
                for n in new_notes
            ]
            details = await asyncio.gather(*tasks)
            for nd in details:
                if nd:
                    await xhs_store.update_xhs_note(nd)
                    nid = nd.get("note_id", "")
                    await download_note_images(nid, nd.get("image_list", []), _IMAGE_DIR)
                    seen_ids.add(nid)
                    collected_note_ids.append(nid)
                    collected_xsec_tokens.append(nd.get("xsec_token", ""))
                    total_notes += 1
            if progress_cb:
                await _safe_call(progress_cb, f"Collected {total_notes} notes")

        try:
            await self._before_request("creator")
            await self._xhs_client.get_all_notes_by_creator(
                user_id=user_id,
                crawl_interval=random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC),
                callback=_on_notes_batch,
                xsec_token=creator_info.xsec_token,
                xsec_source=creator_info.xsec_source or "pc_feed",
            )
        except Exception as exc:
            if _is_captcha_error(exc):
                raise CaptchaException(str(exc)) from exc
            raise

        if enable_comments:
            for nid, tok in zip(collected_note_ids, collected_xsec_tokens):
                cnt = await self._fetch_and_store_comments(
                    nid,
                    tok,
                    max_comments,
                    progress_cb=progress_cb,
                )
                total_comments += cnt
                if progress_cb:
                    await _safe_call(progress_cb, f"Collected {total_notes} notes, {total_comments} comments")

        total_comments_in_db = 0
        if os.path.exists(SQLITE_DB_PATH):
            async with aiosqlite.connect(SQLITE_DB_PATH) as _db:
                cur = await _db.execute(
                    "SELECT COUNT(*) FROM xhs_note_comment WHERE note_id IN "
                    "(SELECT note_id FROM xhs_note WHERE user_id=?)",
                    (user_id,),
                )
                row = await cur.fetchone()
                total_comments_in_db = row[0] if row else 0

        return {
            "notes_count": total_notes,
            "comments_count": total_comments,
            "total_notes_in_db": len(seen_ids),
            "total_comments_in_db": total_comments_in_db,
        }

    async def _fetch_note_detail(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[Dict]:
        async with semaphore:
            try:
                await self._before_request("detail")
                nd = await self._xhs_client.get_note_by_id(note_id, xsec_source, xsec_token)
                if not nd:
                    await self._before_request("detail")
                    nd = await self._xhs_client.get_note_by_id_from_html(
                        note_id, xsec_source, xsec_token, enable_cookie=True
                    )
                if nd:
                    nd.update({"xsec_token": xsec_token, "xsec_source": xsec_source})
                await asyncio.sleep(random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC))
                return nd
            except CaptchaException:
                raise
            except Exception as exc:
                root_exc = _unwrap_retry_error(exc)
                if _is_captcha_error(root_exc):
                    raise CaptchaException(str(root_exc)) from root_exc
                logger.warning(
                    f"[fetch_note_detail] note_id={note_id} "
                    f"err={redact_sensitive_text(exc)}"
                )
                return None

    async def _fetch_and_store_comments(
        self,
        note_id: str,
        xsec_token: str,
        max_count: int,
        include_replies: bool = False,
        reuse_existing: bool = True,
        progress_cb: Optional[Callable[[str], Any]] = None,
    ) -> int:
        if not note_id:
            return 0
        # Reuse comments already in DB (shared across keywords) 鈥?skip network request
        if reuse_existing and os.path.exists(SQLITE_DB_PATH):
            async with aiosqlite.connect(SQLITE_DB_PATH) as _cdb:
                _cur = await _cdb.execute(
                    "SELECT COUNT(*) FROM xhs_note_comment WHERE note_id=?", (note_id,)
                )
                _row = await _cur.fetchone()
                if _row and _row[0] > 0:
                    logger.info(
                        f"[fetch_comments] note_id={note_id} already has {_row[0]} comments, reusing"
                    )
                    return _row[0]
        count = 0
        try:
            # callback signature is (note_id, comments) per client.py
            async def _cb(nid: str, comments: List[Dict]):
                nonlocal count
                if progress_cb:
                    await _safe_call(
                        progress_cb,
                        f"Preparing comments for {nid}: {count}/{max_count}",
                        count,
                    )
                await xhs_store.batch_update_xhs_note_comments(nid, comments)
                count += len(comments)
                if progress_cb:
                    await _safe_call(
                        progress_cb,
                        f"Fetched comments for {nid}: {count}/{max_count}",
                        count,
                    )

            await self._before_request("comment")
            await self._xhs_client.get_note_all_comments(
                note_id=note_id,
                xsec_token=xsec_token,
                crawl_interval=random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC),
                callback=_cb,
                max_count=max_count,
                include_sub_comments=include_replies,
            )
        except CaptchaException:
            raise
        except ExecutorLeaseLost:
            raise
        except Exception as exc:
            root_exc = _unwrap_retry_error(exc)
            if _is_captcha_error(root_exc):
                raise CaptchaException(str(root_exc)) from root_exc
            logger.warning(
                f"[fetch_comments] note_id={note_id} err={redact_sensitive_text(exc)}"
            )
        return count

    async def _do_crawl_notes(
        self,
        note_items: List[Dict],
        max_comments: int,
        include_replies: bool,
        progress_cb,
    ) -> Dict:
        config.SAVE_DATA_OPTION = "sqlite"
        await create_tables("sqlite")
        crawler_type_var.set("search")

        total = len(note_items)
        done = 0
        failed = 0
        total_comments = 0

        for item in note_items:
            note_input = item.get("note_input", "").strip()
            if not note_input:
                continue

            # Parse note_id and xsec_token from URL or plain ID
            if note_input.startswith("http"):
                info = parse_note_info_from_note_url(note_input)
                note_id = info.note_id
                xsec_token = info.xsec_token
                xsec_source = info.xsec_source or "pc_search"
            else:
                note_id = note_input
                xsec_token = ""
                xsec_source = "pc_search"

            source_keyword_var.set(note_id)
            try:
                sem = asyncio.Semaphore(1)
                nd = await self._fetch_note_detail(note_id, xsec_source, xsec_token, sem)
                # Fallback: use Playwright browser to navigate to note URL (handles missing xsec_token)
                if not nd:
                    logger.info(f"[crawl_notes] API/HTML failed for {note_id}, trying browser fallback")
                    nd = await self._fetch_note_via_browser(note_id, xsec_token, xsec_source)
                if nd:
                    if "note_id" not in nd or not nd["note_id"]:
                        nd["note_id"] = note_id
                    await xhs_store.update_xhs_note(nd)
                    await download_note_images(note_id, nd.get("image_list", []), _IMAGE_DIR)
                    done += 1
                    if max_comments > 0:
                        async def _comment_progress(
                            message: str,
                            note_comment_count: int = 0,
                        ):
                            if progress_cb:
                                await _safe_call(
                                    progress_cb,
                                    message,
                                    done,
                                    total_comments + note_comment_count,
                                )

                        total_comments += await self._fetch_and_store_comments(
                            note_id,
                            xsec_token,
                            max_comments,
                            include_replies=include_replies,
                            reuse_existing=not include_replies,
                            progress_cb=_comment_progress,
                        )
                else:
                    logger.warning(f"[crawl_notes] all methods failed for note_id={note_id}, URL may lack xsec_token")
                    failed += 1
            except CaptchaException:
                raise
            except ExecutorLeaseLost:
                raise
            except Exception as exc:
                logger.warning(
                    f"[crawl_notes] note_id={note_id} err={redact_sensitive_text(exc)}"
                )
                failed += 1

            if progress_cb:
                await _safe_call(
                    progress_cb,
                    f"Collected {done}/{total} notes, {total_comments} comments, failed {failed}",
                    done,
                    total_comments,
                )
            await asyncio.sleep(random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC))

        return {
            "notes_count": done,
            "comments_count": total_comments,
            "failed_count": failed,
            "total_notes_in_db": done,
        }

    async def _fetch_note_via_browser(self, note_id: str, xsec_token: str = "", xsec_source: str = "pc_search") -> Optional[Dict]:
        """Navigate Playwright browser to the note page and extract note data via JS state."""
        if not self._page:
            logger.warning(f"[fetch_note_via_browser] no page available for note_id={note_id}")
            return None
        try:
            import json as _json
            import humps

            if xsec_token:
                url = f"{self._index_url}/explore/{note_id}?xsec_token={xsec_token}&xsec_source={xsec_source}"
            else:
                url = f"{self._index_url}/explore/{note_id}"

            logger.info(f"[fetch_note_via_browser] navigating note_id={note_id}")
            # domcontentloaded avoids hanging on SPA background network requests
            await self._before_request("detail")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(config.CRAWLER_MIN_SLEEP_SEC, config.CRAWLER_MAX_SLEEP_SEC))

            # Wait until window.__INITIAL_STATE__.note.noteDetailMap is populated by JS
            js_ready = "() => !!(window.__INITIAL_STATE__ && window.__INITIAL_STATE__.note && Object.keys(window.__INITIAL_STATE__.note.noteDetailMap || {}).length > 0)"
            try:
                await self._page.wait_for_function(js_ready, timeout=10000)
            except Exception:
                # If still not ready after 10 s, give it one last sleep and try anyway
                await asyncio.sleep(3)

            actual_url = self._page.url
            logger.info(
                "[fetch_note_via_browser] actual URL after nav: "
                f"{redact_sensitive_text(actual_url)}"
            )
            if "captcha" in actual_url.lower() or "website-login/captcha" in actual_url:
                raise CaptchaException(
                    f"Browser CAPTCHA detected for account {self.account_id}, URL: {actual_url}"
                )
            if "/404" in actual_url or "error_code=300031" in actual_url:
                logger.warning(
                    f"[fetch_note_via_browser] note_id={note_id} redirected to 404 鈥?"
                    "URL must include xsec_token (copy link from search results, not address bar)"
                )
                return None

            # Extract JS runtime state
            state_str = await self._page.evaluate(
                "() => typeof window.__INITIAL_STATE__ !== 'undefined' ? JSON.stringify(window.__INITIAL_STATE__) : null"
            )
            logger.info(f"[fetch_note_via_browser] state_str None={state_str is None}, len={len(state_str) if state_str else 0}")

            if state_str:
                raw = _json.loads(state_str)
                state = humps.decamelize(raw)
                logger.info(f"[fetch_note_via_browser] state top-keys: {list(state.keys())}")
                note_map = state.get("note", {}).get("note_detail_map", {})
                logger.info(f"[fetch_note_via_browser] note_map keys: {list(note_map.keys())}")
                nd = None
                if note_id in note_map:
                    nd = note_map[note_id].get("note")
                # Fallback: pick the only entry in the map regardless of key
                if not nd and len(note_map) == 1:
                    only = next(iter(note_map.values()))
                    nd = only.get("note") if isinstance(only, dict) else None
                if nd:
                    nd["note_id"] = nd.get("note_id") or note_id
                    nd.update({"xsec_token": xsec_token, "xsec_source": xsec_source})
                    logger.info(f"[fetch_note_via_browser] SUCCESS via JS state for {note_id}")
                    return nd
                logger.warning(f"[fetch_note_via_browser] note_id not found in note_map for {note_id}")

            # Last resort: HTML parsing
            html = await self._page.content()
            logger.info(f"[fetch_note_via_browser] HTML len={len(html)}, has noteDetailMap={'noteDetailMap' in html}")
            nd = self._xhs_client._extractor.extract_note_detail_from_html(note_id, html)
            if nd:
                nd.update({"xsec_token": xsec_token, "xsec_source": xsec_source})
                logger.info(f"[fetch_note_via_browser] SUCCESS via HTML for {note_id}")
            else:
                logger.warning(f"[fetch_note_via_browser] HTML extraction also failed for {note_id}")
            return nd
        except CaptchaException:
            raise
        except Exception as exc:
            logger.warning(
                f"[fetch_note_via_browser] EXCEPTION note_id={note_id}: "
                f"{redact_sensitive_text(exc)}"
            )
            return None

    async def get_qrcode_for_web(self) -> dict:
        """Navigate to XHS login page and return QR code as base64 for web UI."""
        from tools.crawler_util import find_login_qrcode
        if not self._page or not self._browser_context:
                return {"error": "QR code not found; check whether the account is already logged in or the page loaded correctly."}
        try:
            await self._page.goto(self._index_url, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            qrcode_selector = "xpath=//img[@class='qrcode-img']"
            base64_img = await find_login_qrcode(self._page, selector=qrcode_selector)
            if not base64_img:
                try:
                    login_btn = self._page.locator(
                        "xpath=//*[@id='app']/div[1]/div[2]/div[1]/ul/div[1]/button"
                    )
                    await login_btn.click()
                    await asyncio.sleep(1)
                except Exception:
                    pass
                base64_img = await find_login_qrcode(self._page, selector=qrcode_selector)
            if not base64_img:
                return {"error": "QR code not found; check whether the account is already logged in or the page loaded correctly."}
            current_cookies = await self._browser_context.cookies()
            _, cookie_dict = convert_cookies(current_cookies)
            session_before = cookie_dict.get("web_session", "")
            self.status = "waiting_qrcode"
            self.message = "Waiting for QR login..."
            return {"qrcode": base64_img, "session_before": session_before}
        except Exception as exc:
            safe_error = redact_sensitive_text(exc)
            logger.error(f"[get_qrcode_for_web] {safe_error}")
            return {"error": safe_error}

    async def check_qrcode_login_done(self, session_before: str) -> dict:
        """Poll whether QR code login completed. Returns {done, cookie} or {done:False}."""
        if not self._page or not self._browser_context:
            return {"done": False, "error": "Engine not started"}
        try:
            # Check UI element
            user_profile_sel = "xpath=//a[contains(@href, '/user/profile/')]"
            try:
                is_visible = await self._page.is_visible(user_profile_sel, timeout=500)
            except Exception:
                is_visible = False
            # Check cookie change
            current_cookies = await self._browser_context.cookies()
            _, cookie_dict = convert_cookies(current_cookies)
            current_session = cookie_dict.get("web_session", "")
            logged_in = is_visible or (current_session and current_session != session_before)
            if logged_in:
                await self._refresh_client()
                cookie_str = self._xhs_client.headers.get("Cookie", "")
                if cookie_str and ("web_session=" in cookie_str or "a1=" in cookie_str):
                    try:
                        verified = await self._xhs_client.pong()
                    except Exception as exc:
                        logger.warning(
                            "[check_qrcode_login_done] post-login pong failed: "
                            f"{redact_sensitive_text(exc)}"
                        )
                        return {
                            "done": True,
                            "verified": False,
                            "cookie": cookie_str,
                            "error": f"post-login verification failed: {redact_sensitive_text(exc)}",
                        }
                    if verified:
                        self.status = "ready"
                        self.message = "QR login succeeded"
                        return {"done": True, "verified": True, "cookie": cookie_str}
                    return {
                        "done": True,
                        "verified": False,
                        "cookie": cookie_str,
                        "error": "post-login verification failed",
                    }
            return {"done": False}
        except Exception as exc:
            logger.warning(
                f"[check_qrcode_login_done] {redact_sensitive_text(exc)}"
            )
            return {"done": False}

async def _load_existing_note_ids(field: str, value: str) -> set:
    """Return the set of note_ids already saved for a keyword or user_id."""
    if field not in {"source_keyword", "user_id"}:
        raise ValueError(f"Unsupported note lookup field: {field}")
    if not os.path.exists(SQLITE_DB_PATH):
        return set()
    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        cursor = await db.execute(
            f"SELECT note_id FROM xhs_note WHERE {field}=?", (value,)
        )
        rows = await cursor.fetchall()
    return {r[0] for r in rows}


async def _safe_call(fn: Callable, *args):
    try:
        result = fn(*args)
        if asyncio.iscoroutine(result):
            await result
    except ExecutorLeaseLost:
        raise
    except Exception:
        pass
