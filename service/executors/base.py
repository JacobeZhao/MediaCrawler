from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional


ProgressCallback = Callable[..., Awaitable[bool]]
CheckpointCallback = Callable[[Dict[str, Any]], Awaitable[bool]]


@dataclass(frozen=True)
class ProviderReadiness:
    enabled: bool
    ready: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "ready": self.ready,
            "reason": self.reason,
            **self.details,
        }


@dataclass
class ExecutionContext:
    task_id: int
    progress_callback: ProgressCallback
    checkpoint_callback: CheckpointCallback

    async def progress(
        self,
        message: str,
        *,
        stage: str = "running",
        notes_count: Optional[int] = None,
        comments_count: Optional[int] = None,
        lease_seconds: Optional[int] = None,
    ) -> bool:
        return await self.progress_callback(
            message=message,
            stage=stage,
            notes_count=notes_count,
            comments_count=comments_count,
            lease_seconds=lease_seconds,
        )

    async def checkpoint(self, data: Dict[str, Any]) -> bool:
        return await self.checkpoint_callback(data)


class ExecutorPaused(Exception):
    def __init__(
        self,
        message: str,
        *,
        error: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error = error
        self.retry_after_seconds = retry_after_seconds


class ExecutorLeaseLost(Exception):
    pass


class TaskExecutor(ABC):
    provider: str

    @abstractmethod
    async def readiness(self) -> ProviderReadiness:
        raise NotImplementedError

    @abstractmethod
    async def execute(
        self,
        task: Dict[str, Any],
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        raise NotImplementedError
