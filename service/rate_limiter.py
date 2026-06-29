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
        self._request_count_by_account: DefaultDict[Hashable, int] = defaultdict(int)
        self._penalty_until_by_account: DefaultDict[Hashable, float] = defaultdict(float)

    async def acquire(self, account_id: int | None, endpoint: str) -> None:
        async with self._lock:
            now = time.monotonic()
            account_key = self._account_key(account_id)
            wait_for = max(
                self._remaining(now, self._last_global, settings.crawler_global_min_interval_sec),
                self._remaining(
                    now,
                    self._last_by_account[account_key],
                    settings.crawler_account_min_interval_sec,
                ),
                self._remaining(now, self._last_by_endpoint[endpoint], self._endpoint_interval(endpoint)),
                max(0.0, self._penalty_until_by_account[account_key] - now),
            )
            if wait_for > 0:
                await asyncio.sleep(wait_for + random.uniform(0, min(1.5, wait_for * 0.2)))
                now = time.monotonic()
            if self._should_budget_rest(account_key):
                rest_for = random.uniform(
                    settings.crawler_account_budget_rest_min_sec,
                    settings.crawler_account_budget_rest_max_sec,
                )
                await asyncio.sleep(max(0.0, rest_for))
                now = time.monotonic()
                self._request_count_by_account[account_key] = 0
            self._last_global = now
            self._last_by_account[account_key] = now
            self._last_by_endpoint[endpoint] = now
            self._request_count_by_account[account_key] += 1

    async def penalize(self, account_id: int | None, seconds: float | None = None) -> None:
        duration = seconds if seconds is not None else settings.crawler_risk_backoff_sec
        if duration <= 0:
            return
        async with self._lock:
            account_key = self._account_key(account_id)
            self._penalty_until_by_account[account_key] = max(
                self._penalty_until_by_account[account_key],
                time.monotonic() + duration,
            )
            self._request_count_by_account[account_key] = 0

    def snapshot(self) -> dict:
        now = time.monotonic()
        return {
            "global_min_interval_sec": settings.crawler_global_min_interval_sec,
            "account_min_interval_sec": settings.crawler_account_min_interval_sec,
            "endpoint_min_interval_sec": {
                "search": settings.crawler_search_min_interval_sec,
                "detail": settings.crawler_detail_min_interval_sec,
                "comment": settings.crawler_comment_min_interval_sec,
                "creator": settings.crawler_creator_min_interval_sec,
            },
            "account_request_budget": settings.crawler_account_request_budget,
            "account_request_counts": {
                str(key): value for key, value in self._request_count_by_account.items()
            },
            "active_penalties_sec": {
                str(key): max(0, int(until - now))
                for key, until in self._penalty_until_by_account.items()
                if until > now
            },
        }

    @staticmethod
    def _remaining(now: float, last_at: float, interval: float) -> float:
        if interval <= 0 or last_at <= 0:
            return 0.0
        return max(0.0, interval - (now - last_at))

    @staticmethod
    def _account_key(account_id: int | None) -> Hashable:
        return account_id if account_id is not None else "default"

    def _should_budget_rest(self, account_key: Hashable) -> bool:
        budget = settings.crawler_account_request_budget
        return budget > 0 and self._request_count_by_account[account_key] >= budget

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
