from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class RequestRecord:
    endpoint: str
    request_id: Optional[str]
    http_status: Optional[int]
    business_code: Optional[int]
    duration_ms: int
    attempt: int
    billed: bool
    error_type: Optional[str] = None
    outcome_unknown: bool = False


@dataclass(frozen=True)
class ApiEnvelope:
    code: int
    message: Optional[str]
    data: Any
    record_time: Optional[str]
    request_id: Optional[str]
    endpoint: str
    http_status: int
    duration_ms: int
    attempt: int = 1

    @property
    def billed(self) -> bool:
        return self.code == 0

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        endpoint: str,
        http_status: int,
        duration_ms: int,
        attempt: int,
    ) -> "ApiEnvelope":
        if "code" not in payload:
            raise ValueError("JustOneAPI response is missing code")
        try:
            code = int(payload["code"])
        except (TypeError, ValueError) as exc:
            raise ValueError("JustOneAPI response code is not an integer") from exc
        message = payload.get("message")
        return cls(
            code=code,
            message=None if message is None else str(message),
            data=payload.get("data"),
            record_time=(
                None
                if payload.get("recordTime") is None
                else str(payload.get("recordTime"))
            ),
            request_id=(
                None
                if payload.get("requestId") is None
                else str(payload.get("requestId"))
            ),
            endpoint=endpoint,
            http_status=http_status,
            duration_ms=duration_ms,
            attempt=attempt,
        )

    def request_record(self) -> RequestRecord:
        return RequestRecord(
            endpoint=self.endpoint,
            request_id=self.request_id,
            http_status=self.http_status,
            business_code=self.code,
            duration_ms=self.duration_ms,
            attempt=self.attempt,
            billed=self.billed,
        )
