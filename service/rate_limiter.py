# -*- coding: utf-8 -*-
"""Conservative in-process rate limiter for XHS crawl requests."""
import asyncio
import random
import time
from collections import defaultdict
from typing import DefaultDict, Hashable

from config.settings import settings


class CrawlRateLimiter:
    """Serializes request timing across global, account, and endpoint scopes."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_global = 0.0
        self._last_by_account: DefaultDict[Hashable, float] = defaultdict(float)
        self._last_by_endpoint: DefaultDict[str, float] = defaultdict(float)

    async def acquire(self, account_id: int | None, endpoint: str) -> None:
        async with self._lock:
            now = time.monotonic()
            wait_for = max(
                self._remaining(now, self._last_global, settings.crawler_global_min_interval_sec),
                self._remaining(
                    now,
                    self._last_by_account[self._account_key(account_id)],
                    settings.crawler_account_min_interval_sec,
                ),
                self._remaining(now, self._last_by_endpoint[endpoint], self._endpoint_interval(endpoint)),
            )
            if wait_for > 0:
                await asyncio.sleep(wait_for + random.uniform(0, min(1.5, wait_for * 0.2)))
                now = time.monotonic()
            self._last_global = now
            self._last_by_account[self._account_key(account_id)] = now
            self._last_by_endpoint[endpoint] = now

    @staticmethod
    def _remaining(now: float, last_at: float, interval: float) -> float:
        if interval <= 0 or last_at <= 0:
            return 0.0
        return max(0.0, interval - (now - last_at))

    @staticmethod
    def _account_key(account_id: int | None) -> Hashable:
        return account_id if account_id is not None else "default"

    @staticmethod
    def _endpoint_interval(endpoint: str) -> float:
        if endpoint == "search":
            return settings.crawler_search_min_interval_sec
        if endpoint == "detail":
            return settings.crawler_detail_min_interval_sec
        if endpoint == "comment":
            return settings.crawler_comment_min_interval_sec
        if endpoint == "creator":
            return settings.crawler_creator_min_interval_sec
        return settings.crawler_global_min_interval_sec


rate_limiter = CrawlRateLimiter()
