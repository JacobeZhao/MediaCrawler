import os
import shutil
import time
import uuid
from typing import Dict, Optional

from fastapi import HTTPException

from .. import service_db as sdb
from ..account_pool import AccountPool
from ..crawler_engine import XHSCrawlerEngine
from ..schemas.accounts import AccountCookieRequest, AccountQrcodeStartRequest, AccountRequest
from ..task_manager import TaskManager


class QrSessionService:
    def __init__(self, root_dir: str, ttl_seconds: int = 300):
        self._root_dir = root_dir
        self._ttl_seconds = ttl_seconds
        self._sessions: Dict[str, dict] = {}

    async def cleanup_expired(self):
        now = time.monotonic()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session["created_at"] > self._ttl_seconds
        ]
        for sid in expired:
            await self.cancel(sid)

    async def start(self, name: str) -> dict:
        await self.cleanup_expired()
        if not name.strip():
            raise HTTPException(400, "Account name cannot be empty.")

        session_id = uuid.uuid4().hex[:10]
        temp_dir = os.path.join(self._root_dir, "browser_data", f"qr_session_{session_id}")
        temp_engine = XHSCrawlerEngine(account_id=None, user_data_dir=temp_dir)
        await temp_engine.start()

        result = await temp_engine.get_qrcode_for_web()
        if "error" in result:
            await temp_engine.stop()
            raise HTTPException(400, result["error"])

        self._sessions[session_id] = {
            "engine": temp_engine,
            "name": name.strip(),
            "session_before": result["session_before"],
            "created_at": time.monotonic(),
        }
        return {"session_id": session_id, "qrcode": result["qrcode"]}

    def get(self, session_id: str) -> dict:
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
    ):
        self._pool = pool
        self._qr_sessions = qr_sessions
        self._task_manager = task_manager

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

        account_id = await sdb.add_account(req.name.strip(), req.cookie.strip())
        ok = await self._pool.add_account(account_id, req.name.strip(), req.cookie.strip())
        if not ok:
            await sdb.delete_account(account_id)
            raise HTTPException(400, "Cookie is invalid or account startup failed.")
        await sdb.update_account(account_id, status="active")
        await self._wake_paused_tasks()
        return {"account_id": account_id, "message": f"Account {req.name} added."}

    async def delete_account(self, account_id: int):
        acc = await sdb.get_account(account_id)
        if not acc:
            raise HTTPException(404, "Account not found.")
        await self._pool.remove_account(account_id)
        await sdb.delete_account(account_id)
        return {"message": "Account deleted."}

    async def update_account_cookie(self, account_id: int, req: AccountCookieRequest):
        acc = await sdb.get_account(account_id)
        if not acc:
            raise HTTPException(404, "Account not found.")
        await self._pool.remove_account(account_id)
        ok = await self._pool.add_account(account_id, acc["name"], req.cookie.strip())
        if not ok:
            await self._pool.add_account(account_id, acc["name"], acc["cookie"])
            raise HTTPException(400, "New cookie is invalid.")
        await sdb.update_account(account_id, cookie=req.cookie.strip(), status="active")
        await self._wake_paused_tasks()
        return {"message": "Cookie updated."}

    async def health_check_accounts(self):
        results = await self._pool.health_check_all()
        return {"results": results, "message": f"Checked {len(results)} accounts."}

    async def start_qrcode(self, req: AccountQrcodeStartRequest):
        return await self._qr_sessions.start(req.name)

    async def poll_qrcode(self, session_id: str):
        session = self._qr_sessions.get(session_id)
        eng: XHSCrawlerEngine = session["engine"]
        result = await eng.check_qrcode_login_done(session["session_before"])

        if result.get("done"):
            cookie_str = result.get("cookie", "")
            if not result.get("verified"):
                raise HTTPException(400, result.get("error") or "QR login finished but account verification failed.")
            name = session["name"]
            account_id = await sdb.add_account(name, cookie_str)
            await self._pool.adopt_engine(account_id, eng)
            await sdb.update_account(account_id, status="active")
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
