from __future__ import annotations

from typing import Dict, Iterable

from .base import ProviderReadiness, TaskExecutor


class ExecutorRegistry:
    def __init__(self, executors: Iterable[TaskExecutor]):
        self._executors: Dict[str, TaskExecutor] = {}
        for executor in executors:
            if executor.provider in self._executors:
                raise ValueError(f"Duplicate task executor: {executor.provider}")
            self._executors[executor.provider] = executor

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(self._executors)

    def get(self, provider: str) -> TaskExecutor:
        try:
            return self._executors[provider]
        except KeyError as exc:
            raise ValueError(f"Unknown task provider: {provider}") from exc

    async def readiness(self) -> Dict[str, ProviderReadiness]:
        return {
            provider: await executor.readiness()
            for provider, executor in self._executors.items()
        }
