# -*- coding: utf-8 -*-
"""Global crawl circuit breaker for account-protection pauses."""
from datetime import datetime, timedelta
from typing import Optional

from config.settings import settings
from tools.redaction import redact_sensitive_text
from . import service_db as db

RISK_EVENT_TYPES = ["captcha", "rate_limited", "auth_expired", "permission_denied", "account_error"]


class CrawlCircuitBreaker:
    def __init__(self):
        self._open_until: Optional[datetime] = None
        self._reason = ""

    def is_open(self) -> bool:
        return self.open_until is not None

    @property
    def open_until(self) -> Optional[datetime]:
        if self._open_until and datetime.now() < self._open_until:
            return self._open_until
        self._open_until = None
        self._reason = ""
        return None

    @property
    def reason(self) -> str:
        return self._reason

    async def record_risk_event(
        self,
        event_type: str,
        *,
        account_id: int | None = None,
        task_id: int | None = None,
        message: str | None = None,
    ) -> None:
        await db.add_crawl_event(
            event_type,
            account_id=account_id,
            task_id=task_id,
            error_type=event_type,
            message=redact_sensitive_text(message) if message is not None else None,
        )
        await self.evaluate()

    async def evaluate(self) -> bool:
        since = (datetime.now() - timedelta(seconds=settings.circuit_window_sec)).isoformat()
        count = await db.count_recent_crawl_events(RISK_EVENT_TYPES, since)
        if count >= settings.circuit_error_threshold:
            self._open_until = datetime.now() + timedelta(seconds=settings.circuit_pause_sec)
            self._reason = f"{count} risk events in {settings.circuit_window_sec}s"
            await db.add_crawl_event(
                "circuit_open",
                message=f"{self._reason}; pause until {self._open_until.isoformat()}",
            )
            return True
        return self.is_open()

    def status(self) -> dict:
        open_until = self.open_until
        return {
            "open": open_until is not None,
            "open_until": open_until.isoformat() if open_until else None,
            "reason": self._reason,
        }


circuit_breaker = CrawlCircuitBreaker()
