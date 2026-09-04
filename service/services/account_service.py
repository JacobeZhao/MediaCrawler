import os
import shutil
import time
import uuid
from typing import Dict, Optional

from fastapi import HTTPException

from ..account_pool import AccountPool
from ..crawler_engine import XHSCrawlerEngine
from ..repositories.accounts import AccountRepository
from ..schemas.accounts import (
    AccountCookieRequest,
    AccountProxyRequest,
    AccountQrcodeStartRequest,
    AccountRequest,
    CandidateAccountBulkRequest,
)
from ..task_manager import TaskManager
from ..proxy_config import build_playwright_proxy


async def _get_active_proxy_or_error(
    proxy_id: Optional[int],
    *,
    include_secret: bool = False,
    repository=None,
):
    if not proxy_id:
        return None
    repository = repository if repository is not None else AccountRepository()
    proxy = await repository.get_proxy_profile(proxy_id, include_secret=include_secret)
    if not proxy:
        raise HTTPException(404, "Proxy profile not found.")
    if proxy.get("status") != "active":
        raise HTTPException(400, "Proxy profile is inactive.")
    return proxy


class QrSessionService:
    def __init__(self, root_dir: str, ttl_seconds: int = 300, repository=None):
        self._root_dir = root_dir
        self._ttl_seconds = ttl_seconds
        self._repository = repository if repository is not None else AccountRepository()
        self._sessions: Dict[str, dict] = {}

    async def cleanup_expired(self):
        now = time.monotonic()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session["created_at"] > self._ttl_seconds
        ]
        for sid in expired:
            await self.cancel(sid)

    async def start(self, name: str, proxy_id: Optional[int] = None) -> dict:
        await self.cleanup_expired()
        if not name.strip():
            raise HTTPException(400, "Account name cannot be empty.")

        session_id = uuid.uuid4().hex[:10]
        temp_dir = os.path.join(self._root_dir, "browser_data", f"qr_session_{session_id}")
        proxy_profile = await _get_active_proxy_or_error(
            proxy_id,
            include_secret=True,
            repository=self._repository,
        )
        temp_engine = XHSCrawlerEngine(
            account_id=None,
            user_data_dir=temp_dir,
            proxy_config=build_playwright_proxy(proxy_profile),
        )
        try:
            await temp_engine.start()
            result = await temp_engine.get_qrcode_for_web()
            if "error" in result:
                raise HTTPException(400, result["error"])

            self._sessions[session_id] = {
                "engine": temp_engine,
                "name": name.strip(),
                "proxy_id": proxy_id,
                "session_before": result["session_before"],
                "created_at": time.monotonic(),
            }
            return {"session_id": session_id, "qrcode": result["qrcode"]}
        except BaseException:
            try:
                await temp_engine.stop()
            except BaseException:
                pass
            self._delete_session_dir(session_id)
            raise

    async def get(self, session_id: str) -> dict:
        await self.cleanup_expired()
        session = self._sessions.get(session_id)
        if not session:
            raise HTTPException(404, "QR session not found or expired.")
        return session

    def pop(self, session_id: str) -> dict:
        session = self._sessions.pop(session_id, None)
        if not session:
            raise HTTPException(404, "QR session not found or expired.")
        return session

    async def cancel(self, session_id: str):
        session = self._sessions.pop(session_id, None)
        if session:
            try:
                await session["engine"].stop()
            except Exception:
                pass
            self._delete_session_dir(session_id)

    async def close_all(self):
        for session_id in list(self._sessions):
            await self.cancel(session_id)

    def forget(self, session_id: str):
        self._sessions.pop(session_id, None)

    def _delete_session_dir(self, session_id: str):
        temp_dir = os.path.join(self._root_dir, "browser_data", f"qr_session_{session_id}")
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)


class AccountService:
    def __init__(
        self,
        pool: AccountPool,
        qr_sessions: QrSessionService,
        task_manager: Optional[TaskManager] = None,
        repository=None,
    ):
        self._pool = pool
        self._qr_sessions = qr_sessions
        self._task_manager = task_manager
        self._repository = repository if repository is not None else AccountRepository()

    async def _wake_paused_tasks(self):
        if self._task_manager:
            await self._task_manager.requeue_paused_tasks_now()

    async def list_accounts(self):
        return await self._pool.list_accounts_with_status()

    async def add_account(self, req: AccountRequest):
        if not req.name.strip():
            raise HTTPException(400, "Account name cannot be empty.")
        if not req.cookie.strip():
            raise HTTPException(400, "Cookie cannot be empty.")
        await _get_active_proxy_or_error(req.proxy_id, repository=self._repository)

        account_id = await self._repository.add_account(
            req.name.strip(), req.cookie.strip(), req.proxy_id
        )
        ok = await self._pool.add_account(
            account_id,
            req.name.strip(),
            req.cookie.strip(),
            req.proxy_id,
        )
        if not ok:
            await self._repository.delete_account(account_id)
            raise HTTPException(400, "Cookie is invalid or account startup failed.")
        await self._repository.update_account(account_id, status="active")
        await self._wake_paused_tasks()
        return {"account_id": account_id, "message": f"Account {req.name} added."}

    async def delete_account(self, account_id: int):
        acc = await self._repository.get_account(account_id)
        if not acc:
            raise HTTPException(404, "Account not found.")
        await self._pool.remove_account(account_id)
        await self._repository.delete_account(account_id)
        return {"message": "Account deleted."}

    async def update_account_cookie(self, account_id: int, req: AccountCookieRequest):
        acc = await self._repository.get_account(account_id)
        if not acc:
            raise HTTPException(404, "Account not found.")
        await self._pool.remove_account(account_id)
        ok = await self._pool.add_account(account_id, acc["name"], req.cookie.strip(), acc.get("proxy_id"))
        if not ok:
            await self._pool.add_account(account_id, acc["name"], acc["cookie"], acc.get("proxy_id"))
            raise HTTPException(400, "New cookie is invalid.")
        await self._repository.update_account(
            account_id, cookie=req.cookie.strip(), status="active"
        )
        await self._wake_paused_tasks()
        return {"message": "Cookie updated."}

    async def health_check_accounts(self):
        results = await self._pool.health_check_all()
        return {"results": results, "message": f"Checked {len(results)} accounts."}

    async def start_qrcode(self, req: AccountQrcodeStartRequest):
        return await self._qr_sessions.start(req.name, req.proxy_id)

    async def poll_qrcode(self, session_id: str):
        session = await self._qr_sessions.get(session_id)
        eng: XHSCrawlerEngine = session["engine"]
        result = await eng.check_qrcode_login_done(session["session_before"])

        if result.get("done"):
            cookie_str = result.get("cookie", "")
            if not result.get("verified"):
                raise HTTPException(400, result.get("error") or "QR login finished but account verification failed.")
            name = session["name"]
            proxy_id = session.get("proxy_id")
            account_id = await self._repository.add_account(name, cookie_str, proxy_id)
            await self._pool.adopt_engine(account_id, eng)
            await self._repository.update_account(account_id, status="active")
            self._qr_sessions.forget(session_id)
            await self._wake_paused_tasks()
            return {
                "status": "success",
                "account_id": account_id,
                "name": name,
                "message": f"Account {name} added by QR login.",
            }

        if result.get("error"):
            return {"status": "pending", "message": result["error"]}
        return {"status": "pending", "message": "Waiting for QR login confirmation."}

    async def cancel_qrcode(self, session_id: str):
        await self._qr_sessions.cancel(session_id)
        return {"message": "QR session cancelled."}

    async def list_candidate_accounts(self):
        return await self._repository.list_candidate_accounts()

    async def save_candidate_accounts(self, req: CandidateAccountBulkRequest):
        ids = []
        for item in req.accounts:
            data = item.model_dump()
            data["phone"] = data.get("phone", "").strip()
            data["user_id"] = data.get("user_id", "").strip()
            if not data["phone"] and not data["user_id"]:
                raise HTTPException(400, "Candidate account must include phone or user_id.")
            ids.append(await self._repository.upsert_candidate_account(data))
        return {"candidate_ids": ids, "count": len(ids), "message": f"Saved {len(ids)} candidate accounts."}

    async def delete_candidate_account(self, candidate_id: int):
        await self._repository.delete_candidate_account(candidate_id)
        return {"message": "Candidate account deleted."}

    async def update_account_proxy(self, account_id: int, req: AccountProxyRequest):
        acc = await self._repository.get_account(account_id)
        if not acc:
            raise HTTPException(404, "Account not found.")
        await _get_active_proxy_or_error(req.proxy_id, repository=self._repository)
        if req.restart:
            await self._pool.remove_account(account_id)
            ok = await self._pool.add_account(
                account_id,
                acc["name"],
                acc["cookie"],
                req.proxy_id,
            )
            if not ok:
                await self._pool.add_account(account_id, acc["name"], acc["cookie"], acc.get("proxy_id"))
                raise HTTPException(400, "Account failed to restart with the selected proxy.")
        await self._repository.update_account(account_id, proxy_id=req.proxy_id)
        if req.restart:
            await self._repository.update_account(account_id, status="active")
        return {"message": "Account proxy updated."}
