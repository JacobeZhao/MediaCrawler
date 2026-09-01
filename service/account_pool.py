# -*- coding: utf-8 -*-
"""
Account pool: manages multiple XHSCrawlerEngine instances.
Features: 15-min proactive rotation, cooldown auto-recovery, periodic health check.
"""
import asyncio
import os
import time
from enum import Enum
from datetime import datetime
from typing import Dict, List, Optional

from tools.utils import logger
from tools.redaction import redact_sensitive_text
from config.settings import settings
from . import service_db as sdb
from .crawler_engine import XHSCrawlerEngine
from .proxy_config import build_playwright_proxy, mask_proxy_url

_PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

ROTATION_INTERVAL = 900      # 15 minutes
COOLDOWN_DURATION = settings.account_cooldown_base_sec
HEALTH_CHECK_INTERVAL = settings.account_health_check_interval_sec


def _is_hard_auth_error(error: Optional[str]) -> bool:
    if not error:
        return False
    msg = error.lower()
    hard_markers = (
        "登录已过期",
        "登陆已过期",
        "请登录",
        "没有权限",
        "无权限",
        "未登录",
        "unauthorized",
        "session expired",
        "cookie is invalid",
        "invalid cookie",
        "login expired",
        "not logged in",
    )
    return any(marker in msg for marker in hard_markers)


def _classify_account_error(error: Optional[str], has_login_cookie: bool) -> tuple[str, str]:
    if not error:
        return ("none", "no_action")
    msg = error.lower()
    if _is_hard_auth_error(error):
        return ("auth_expired", "replace_cookie_or_scan_qr")
    if "captcha" in msg or "验证码" in msg or "风控" in msg:
        return ("captcha", "manual_verify_or_wait")
    if "rate" in msg or "429" in msg or "too many" in msg or "频繁" in msg:
        return ("rate_limited", "wait_retry")
    if has_login_cookie:
        return ("temporary_probe_failed", "wait_retry")
    return ("unknown", "replace_cookie_or_scan_qr")


class EngineStatus(str, Enum):
    READY = "ready"
    CAPTCHA = "captcha"
    COOLING_DOWN = "cooling_down"
    INVALID = "invalid"


class AccountPool:
    """
    Wraps a default XHSCrawlerEngine plus zero or more pool engines loaded
    from the `accounts` DB table. Features: CAPTCHA-aware fallback, proactive
    15-min rotation, cooldown auto-recovery, periodic health checks.
    """

    def __init__(self, default_engine: XHSCrawlerEngine):
        self._default = default_engine
        self._pool: Dict[int, XHSCrawlerEngine] = {}   # account_id -> engine
        self._lock = asyncio.Lock()

        self._engine_list: List[XHSCrawlerEngine] = []
        self._current_index: int = 0
        self._last_rotated_at: float = 0.0
        self._cool_until: Dict[int, float] = {}  # id(engine) -> monotonic recovery ts
        self._failure_counts: Dict[int, int] = {}

        self._rotation_task: Optional[asyncio.Task] = None
        self._health_task: Optional[asyncio.Task] = None

    async def start(self):
        accounts = await sdb.get_active_accounts()
        for acc in accounts:
            await self._start_engine(acc["id"], acc["name"], acc["cookie"], acc.get("proxy_id"))
        self._rebuild_engine_list()
        self._rotation_task = asyncio.create_task(
            self._rotation_loop(), name="account-rotation"
        )
        self._health_task = asyncio.create_task(
            self._health_loop(), name="account-health"
        )

    async def stop(self):
        tasks = []
        for task in (self._rotation_task, self._health_task):
            if task:
                task.cancel()
                tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for eng in list(self._pool.values()):
            try:
                await eng.stop()
            except Exception:
                pass
        self._pool.clear()
        self._engine_list.clear()

    async def get_healthy_engine(self) -> Optional[XHSCrawlerEngine]:
        """Return the current-rotation ready engine; None if all unavailable."""
        self._recover_cooled_engines()

        n = len(self._engine_list)
        for i in range(n):
            idx = (self._current_index + i) % n
            eng = self._engine_list[idx]
            if eng.status == EngineStatus.READY.value:
                return eng

        if self._default.status == EngineStatus.READY.value:
            return self._default

        return None

    async def mark_captcha(self, engine: XHSCrawlerEngine):
        """Mark an engine's account as captcha-blocked."""
        engine.status = EngineStatus.CAPTCHA.value
        engine.message = "account captcha required"
        for acc_id, eng in self._pool.items():
            if eng is engine:
                await sdb.update_account(
                    acc_id,
                    status=sdb.AccountStatus.CAPTCHA,
                    captcha_count=await self._increment_captcha_count(acc_id),
                    last_checked=datetime.now().isoformat(),
                )
                logger.warning(f"[AccountPool] account_id={acc_id} marked captcha")
                return
        logger.warning("[AccountPool] default engine marked captcha")

    async def mark_temporarily_unavailable(
        self, engine: XHSCrawlerEngine, duration: Optional[int] = None
    ):
        """Mark engine as cooling-down for `duration` seconds."""
        duration = duration or self._next_cooldown_duration(engine)
        engine.status = EngineStatus.COOLING_DOWN.value
        engine.message = f"account temporarily unavailable; retry after {duration}s"
        self._cool_until[id(engine)] = time.monotonic() + duration
        if engine.account_id is not None:
            await sdb.update_account(
                engine.account_id,
                status=sdb.AccountStatus.COOLING_DOWN,
                last_checked=datetime.now().isoformat(),
            )
        logger.warning(
            f"[AccountPool] engine account_id={engine.account_id} "
            f"cooling down for {duration}s"
        )

    async def add_account(
        self,
        account_id: int,
        name: str,
        cookie: str,
        proxy_id: Optional[int] = None,
    ) -> bool:
        ok = await self._start_engine(account_id, name, cookie, proxy_id)
        if ok:
            self._rebuild_engine_list()
        return ok

    async def adopt_engine(self, account_id: int, engine: XHSCrawlerEngine):
        """Add an already-authenticated engine to the pool."""
        engine.account_id = account_id
        async with self._lock:
            self._pool[account_id] = engine
        self._rebuild_engine_list()

    async def remove_account(self, account_id: int):
        async with self._lock:
            eng = self._pool.pop(account_id, None)
        if eng:
            try:
                await eng.stop()
            except Exception:
                pass
            self._rebuild_engine_list()

    async def health_check_all(self) -> List[Dict]:
        results = []
        for acc_id, eng in list(self._pool.items()):
            if eng.status == "crawling":
                results.append({
                    "account_id": acc_id,
                    "ok": True,
                    "has_login_cookie": True,
                    "status": eng.status,
                    "error": "skipped health check while crawling",
                })
                continue
            ok = False
            has_login_cookie = False
            error = None
            probe = await eng.probe_login()
            ok = bool(probe["ok"])
            has_login_cookie = bool(probe["has_login_cookie"])
            error = probe["error"]

            is_captcha = eng.status == EngineStatus.CAPTCHA.value
            is_cooling_down = eng.status == EngineStatus.COOLING_DOWN.value
            hard_auth_error = _is_hard_auth_error(error)
            permission_denied = error and ("没有权限" in error or "无权限" in error)
            usable = ok and not hard_auth_error and not permission_denied
            if ok:
                new_status = sdb.AccountStatus.ACTIVE
                eng.status = EngineStatus.READY.value
                self._failure_counts.pop(id(eng), None)
            elif is_captcha:
                new_status = sdb.AccountStatus.CAPTCHA
            elif is_cooling_down:
                new_status = sdb.AccountStatus.COOLING_DOWN
            elif has_login_cookie and not hard_auth_error and not permission_denied:
                new_status = sdb.AccountStatus.COOLING_DOWN
                eng.status = EngineStatus.COOLING_DOWN.value
                eng.message = "login probe failed; cooling down before retry"
                self._cool_until[id(eng)] = time.monotonic() + self._next_cooldown_duration(eng)
            else:
                new_status = sdb.AccountStatus.INVALID
            if not usable and not is_captcha and not is_cooling_down and new_status == sdb.AccountStatus.INVALID:
                eng.status = EngineStatus.INVALID.value
            await sdb.update_account(
                acc_id,
                status=new_status,
                last_checked=datetime.now().isoformat(),
            )
            error_type, next_action = _classify_account_error(error, has_login_cookie)
            results.append({
                "account_id": acc_id,
                "ok": ok,
                "has_login_cookie": has_login_cookie,
                "status": new_status.value,
                "error": error,
                "error_type": error_type,
                "next_action": next_action,
            })
        return results

    async def list_accounts_with_status(self) -> List[Dict]:
        db_accounts = await sdb.list_accounts()
        out = []
        for acc in db_accounts:
            eng = self._pool.get(acc["id"])
            runtime_status = eng.status if eng else acc["status"]
            cookie_preview = _cookie_preview(acc["cookie"])
            proxy_profile = await sdb.get_proxy_profile(acc.get("proxy_id"), include_secret=False)
            out.append({
                "id": acc["id"],
                "name": acc["name"],
                "proxy_id": acc.get("proxy_id"),
                "proxy_name": proxy_profile.get("name") if proxy_profile else "",
                "proxy_server": mask_proxy_url(proxy_profile),
                "proxy_status": proxy_profile.get("status") if proxy_profile else "",
                "status": acc["status"],
                "runtime_status": runtime_status,
                "captcha_count": acc["captcha_count"],
                "last_checked": acc["last_checked"],
                "created_at": acc["created_at"],
                "cookie_preview": cookie_preview,
                "message": eng.message if eng else "",
            })
        return out

    def get_default_engine(self) -> XHSCrawlerEngine:
        return self._default

    def pool_size(self) -> int:
        return len(self._pool)

    def ready_count(self) -> int:
        return sum(1 for eng in self._engine_list if eng.status == EngineStatus.READY.value)

    def has_ready_engine(self) -> bool:
        return self.ready_count() > 0 or self._default.status == EngineStatus.READY.value

    async def _rotation_loop(self):
        """Proactively rotate active engine every ROTATION_INTERVAL seconds."""
        while True:
            try:
                await asyncio.sleep(ROTATION_INTERVAL)
                self._advance_rotation_index()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    f"[AccountPool] rotation_loop error: {redact_sensitive_text(exc)}"
                )

    async def _health_loop(self):
        """Periodically ping all pool engines and recover cooled-down ones."""
        while True:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                self._recover_cooled_engines()
                await self.health_check_all()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    f"[AccountPool] health_loop error: {redact_sensitive_text(exc)}"
                )

    def _rebuild_engine_list(self):
        self._engine_list = list(self._pool.values())
        self._current_index = 0

    def _advance_rotation_index(self):
        n = len(self._engine_list)
        if n == 0:
            return
        self._current_index = (self._current_index + 1) % n
        eng = self._engine_list[self._current_index]
        logger.info(
            f"[AccountPool] rotating to engine index={self._current_index} "
            f"account_id={eng.account_id} status={eng.status}"
        )
        self._last_rotated_at = time.monotonic()

    def _recover_cooled_engines(self):
        now = time.monotonic()
        for eng in list(self._pool.values()) + [self._default]:
            eid = id(eng)
            if eng.status == EngineStatus.COOLING_DOWN.value and eid in self._cool_until:
                if now >= self._cool_until[eid]:
                    eng.status = EngineStatus.COOLING_DOWN.value
                    eng.message = "cooldown finished; health check pending"
                    del self._cool_until[eid]
                    logger.info(
                        f"[AccountPool] engine account_id={eng.account_id} "
                        "cooldown finished; awaiting health check"
                    )

    def _next_cooldown_duration(self, engine: XHSCrawlerEngine) -> int:
        eid = id(engine)
        failures = self._failure_counts.get(eid, 0) + 1
        self._failure_counts[eid] = failures
        duration = settings.account_cooldown_base_sec * (2 ** max(0, failures - 1))
        return int(min(duration, settings.account_cooldown_max_sec))

    async def _start_engine(
        self,
        account_id: int,
        name: str,
        cookie: str,
        proxy_id: Optional[int] = None,
    ) -> bool:
        user_data_dir = os.path.join(_PROJECT_ROOT, "browser_data", f"account_{account_id}")
        os.makedirs(user_data_dir, exist_ok=True)
        proxy_profile = await sdb.get_proxy_profile(proxy_id, include_secret=True)
        if proxy_id and not proxy_profile:
            logger.warning(
                f"[AccountPool] account_id={account_id} proxy_id={proxy_id} not found; skip engine startup"
            )
            return False
        if proxy_profile and proxy_profile.get("status") != "active":
            logger.warning(
                f"[AccountPool] account_id={account_id} proxy_id={proxy_id} inactive; skip engine startup"
            )
            return False
        proxy_config = build_playwright_proxy(proxy_profile)
        eng = XHSCrawlerEngine(
            account_id=account_id,
            user_data_dir=user_data_dir,
            proxy_config=proxy_config,
        )
        try:
            await eng.start()
            ok = await eng.set_cookie(cookie)
            has_login_cookie = "web_session=" in cookie or "a1=" in cookie
            probe = None if ok else await eng.probe_login()
            hard_auth_error = _is_hard_auth_error(eng.message) or _is_hard_auth_error(
                probe.get("error") if probe else None
            )
            if ok:
                async with self._lock:
                    self._pool[account_id] = eng
                logger.info(
                    f"[AccountPool] account_id={account_id} name={name!r} loaded into pool"
                )
                return True
            logger.warning(
                f"[AccountPool] account_id={account_id} cookie invalid, not adding to pool"
            )
            await sdb.update_account(
                account_id,
                status=sdb.AccountStatus.INVALID,
                last_checked=datetime.now().isoformat(),
            )
            await eng.stop()
            return False
        except Exception as exc:
            logger.error(
                f"[AccountPool] account_id={account_id} start failed: "
                f"{redact_sensitive_text(exc)}"
            )
            try:
                await eng.stop()
            except Exception:
                pass
            return False

    async def _increment_captcha_count(self, account_id: int) -> int:
        acc = await sdb.get_account(account_id)
        return (acc["captcha_count"] or 0) + 1 if acc else 1


def _cookie_preview(cookie: str) -> str:
    if not cookie:
        return ""
    keys = []
    for part in cookie.split(";"):
        name = part.strip().partition("=")[0]
        if name in {"web_session", "a1", "id_token", "xsecappid"}:
            keys.append(name)
    return "has " + ", ".join(keys[:4]) if keys else "cookie saved"
