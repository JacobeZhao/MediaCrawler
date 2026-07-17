from __future__ import annotations

import asyncio
import inspect
import re
from dataclasses import replace
from time import perf_counter
from typing import Any, Awaitable, Callable, Mapping, Optional
from urllib.parse import urlparse

import httpx

from .errors import (
    JustOneApiCredentialError,
    JustOneApiHttpError,
    JustOneApiInvalidRequestError,
    JustOneApiProtocolError,
    JustOneApiRateLimitError,
    JustOneApiTransportError,
    JustOneApiUnknownOutcomeError,
)
from .models import ApiEnvelope, RequestRecord
from .options import (
    NoteType,
    TASK_OPTION_DEFAULTS,
    TRANSPORT_SORT_TYPE_DEFAULT,
    TimeFilter,
)


RequestObserver = Callable[[RequestRecord], Awaitable[None] | None]
BeforeRequest = Callable[[str, int], Awaitable[None] | None]
Sleep = Callable[[float], Awaitable[None]]

_TOKEN_QUERY_RE = re.compile(r"([?&]token=)[^&\s]+", re.IGNORECASE)


def redact_token(value: Any, token: str = "") -> str:
    """Return text safe for logs and exceptions."""
    text = str(value or "")
    if token:
        text = text.replace(token, "[REDACTED]")
    return _TOKEN_QUERY_RE.sub(r"\1[REDACTED]", text)


class JustOneApiClient:
    DEFAULT_BASE_URL = "https://api.justoneapi.com"

    SEARCH_NOTES_V4 = "/api/xiaohongshu/search-note/v4"
    USER_NOTES_V4 = "/api/xiaohongshu/get-user-note-list/v4"
    USER_PROFILE_V4 = "/api/xiaohongshu/get-user/v4"
    NOTE_DETAIL_TEMPLATE = "/api/xiaohongshu/get-note-detail/v{version}"
    NOTE_COMMENTS_V4 = "/api/xiaohongshu/get-note-comment/v4"
    COMMENT_REPLIES_V2 = "/api/xiaohongshu/get-note-sub-comment/v2"
    SHARE_LINK = "/api/xiaohongshu/share-url-transfer/v1"

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_sec: float = 120.0,
        max_retries: int = 2,
        retry_base_sec: float = 2.0,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        sleep: Sleep = asyncio.sleep,
    ):
        normalized_base_url = str(base_url or "").strip().rstrip("/")
        parsed_url = urlparse(normalized_base_url)
        if (
            parsed_url.scheme.lower() != "https"
            or not parsed_url.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("JustOneAPI base_url must be an absolute HTTPS URL")
        if timeout_sec <= 0:
            raise ValueError("JustOneAPI timeout_sec must be positive")
        if max_retries < 0:
            raise ValueError("JustOneAPI max_retries cannot be negative")
        if retry_base_sec < 0:
            raise ValueError("JustOneAPI retry_base_sec cannot be negative")

        self._token = str(token or "").strip()
        self._base_url = normalized_base_url
        self._timeout_sec = float(timeout_sec)
        self._max_retries = int(max_retries)
        self._retry_base_sec = float(retry_base_sec)
        self._sleep = sleep
        self._closed = False
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout_sec),
            transport=transport,
            follow_redirects=False,
            headers={"Accept": "application/json"},
        )

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def timeout_sec(self) -> float:
        return self._timeout_sec

    @property
    def closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> "JustOneApiClient":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._client.aclose()

    async def search_notes_v4(
        self,
        keyword: str,
        *,
        page: int = 1,
        search_id: str = "",
        session_id: str = "",
        sort_type: str = TRANSPORT_SORT_TYPE_DEFAULT,
        note_type: NoteType = TASK_OPTION_DEFAULTS.note_type,
        time_filter: TimeFilter = TASK_OPTION_DEFAULTS.time_filter,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        if page < 1:
            raise ValueError("page must be at least 1")
        return await self.get(
            self.SEARCH_NOTES_V4,
            {
                "keyword": keyword,
                "page": page,
                "searchId": search_id,
                "sessionId": session_id,
                "sortType": sort_type,
                "noteType": note_type,
                "timeFilter": time_filter,
            },
            observer=observer,
            before_request=before_request,
        )

    async def search_notes(
        self,
        keyword: str,
        *,
        page: int = 1,
        sort_type: str = TRANSPORT_SORT_TYPE_DEFAULT,
        note_type: NoteType = TASK_OPTION_DEFAULTS.note_type,
        time_filter: TimeFilter = TASK_OPTION_DEFAULTS.time_filter,
        search_id: Optional[str] = None,
        session_id: Optional[str] = None,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.search_notes_v4(
            keyword,
            page=page,
            search_id=search_id or "",
            session_id=session_id or "",
            sort_type=sort_type,
            note_type=note_type,
            time_filter=time_filter,
            observer=observer,
            before_request=before_request,
        )

    async def user_notes_v4(
        self,
        user_id: str,
        *,
        last_cursor: str = "",
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.USER_NOTES_V4,
            {"userId": user_id, "lastCursor": last_cursor},
            observer=observer,
            before_request=before_request,
        )

    async def creator_notes(
        self,
        user_id: str,
        *,
        cursor: Optional[str] = None,
        xsec_token: Optional[str] = None,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.USER_NOTES_V4,
            {
                "userId": user_id,
                "lastCursor": cursor,
            },
            observer=observer,
            before_request=before_request,
        )

    async def user_profile_v4(
        self,
        user_id: str,
        *,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.USER_PROFILE_V4,
            {"userId": user_id},
            observer=observer,
            before_request=before_request,
        )

    async def user_profile(
        self,
        user_id: str,
        *,
        xsec_token: Optional[str] = None,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.USER_PROFILE_V4,
            {"userId": user_id},
            observer=observer,
            before_request=before_request,
        )

    async def note_detail(
        self,
        note_id: str,
        *,
        version: int = 4,
        xsec_token: Optional[str] = None,
        xsec_source: str = "",
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        if version not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("note detail version must be between 1 and 6")
        return await self.get(
            self.NOTE_DETAIL_TEMPLATE.format(version=version),
            {
                "noteId": note_id,
            },
            observer=observer,
            before_request=before_request,
        )

    async def comments(
        self,
        note_id: str,
        *,
        cursor: Optional[str] = None,
        xsec_token: Optional[str] = None,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.NOTE_COMMENTS_V4,
            {
                "noteId": note_id,
                "lastCursor": cursor,
            },
            observer=observer,
            before_request=before_request,
        )

    async def replies(
        self,
        note_id: str,
        comment_id: str,
        *,
        cursor: Optional[str] = None,
        xsec_token: Optional[str] = None,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.COMMENT_REPLIES_V2,
            {
                "noteId": note_id,
                "commentId": comment_id,
                "lastCursor": cursor,
            },
            observer=observer,
            before_request=before_request,
        )

    async def resolve_share_link(
        self,
        url: str,
        *,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.share_link(
            url,
            observer=observer,
            before_request=before_request,
        )

    async def note_comments_v4(
        self,
        note_id: str,
        *,
        last_cursor: str = "",
        sort: str = "latest",
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.NOTE_COMMENTS_V4,
            {"noteId": note_id, "lastCursor": last_cursor, "sort": sort},
            observer=observer,
            before_request=before_request,
        )

    async def comment_replies_v2(
        self,
        note_id: str,
        root_comment_id: str,
        *,
        last_cursor: str = "",
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.COMMENT_REPLIES_V2,
            {
                "noteId": note_id,
                "commentId": root_comment_id,
                "lastCursor": last_cursor,
            },
            observer=observer,
            before_request=before_request,
        )

    async def share_link(
        self,
        share_url: str,
        *,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        return await self.get(
            self.SHARE_LINK,
            {"shareUrl": share_url},
            observer=observer,
            before_request=before_request,
        )

    async def get(
        self,
        endpoint: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        observer: Optional[RequestObserver] = None,
        before_request: Optional[BeforeRequest] = None,
    ) -> ApiEnvelope:
        if self._closed:
            raise RuntimeError("JustOneAPI client is closed")
        if not self.configured:
            raise JustOneApiCredentialError(
                "access token is not configured",
                endpoint=endpoint,
            )
        if not endpoint.startswith("/") or "://" in endpoint:
            raise ValueError("endpoint must be an absolute path")

        query = {
            key: value
            for key, value in dict(params or {}).items()
            if value is not None and value != ""
        }
        query["token"] = self._token

        for attempt in range(1, self._max_retries + 2):
            await self._notify(before_request, endpoint, attempt)
            started = perf_counter()
            try:
                response = await self._client.get(endpoint, params=query)
            except httpx.ReadTimeout as exc:
                duration_ms = self._duration_ms(started)
                await self._observe_failure(
                    observer,
                    endpoint,
                    duration_ms,
                    attempt,
                    "ReadTimeout",
                    outcome_unknown=True,
                )
                raise JustOneApiUnknownOutcomeError(
                    "response timed out after the request was sent",
                    endpoint=endpoint,
                ) from exc
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                duration_ms = self._duration_ms(started)
                await self._observe_failure(
                    observer,
                    endpoint,
                    duration_ms,
                    attempt,
                    type(exc).__name__,
                )
                if attempt <= self._max_retries:
                    await self._retry_sleep(attempt)
                    continue
                raise JustOneApiTransportError(
                    "could not connect to provider",
                    endpoint=endpoint,
                ) from exc
            except httpx.HTTPError as exc:
                duration_ms = self._duration_ms(started)
                await self._observe_failure(
                    observer,
                    endpoint,
                    duration_ms,
                    attempt,
                    type(exc).__name__,
                    outcome_unknown=True,
                )
                raise JustOneApiUnknownOutcomeError(
                    "connection failed after the request may have been sent",
                    endpoint=endpoint,
                ) from exc

            duration_ms = self._duration_ms(started)
            envelope = self._parse_envelope(
                response,
                endpoint=endpoint,
                duration_ms=duration_ms,
                attempt=attempt,
            )
            if envelope is not None:
                await self._notify(observer, envelope.request_record())
                # Business failures remain structured so the executor can first
                # persist provider request metadata and then apply task policy.
                return envelope

            await self._observe_failure(
                observer,
                endpoint,
                duration_ms,
                attempt,
                "InvalidResponse",
                http_status=response.status_code,
            )
            if response.status_code >= 500 and attempt <= self._max_retries:
                await self._retry_sleep(attempt)
                continue
            raise self._http_error(response.status_code, endpoint)

        raise AssertionError("unreachable")

    def _parse_envelope(
        self,
        response: httpx.Response,
        *,
        endpoint: str,
        duration_ms: int,
        attempt: int,
    ) -> Optional[ApiEnvelope]:
        try:
            payload = response.json()
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(payload, Mapping):
            return None
        try:
            envelope = ApiEnvelope.from_payload(
                payload,
                endpoint=endpoint,
                http_status=response.status_code,
                duration_ms=duration_ms,
                attempt=attempt,
            )
        except ValueError:
            return None
        return replace(
            envelope,
            message=(
                None
                if envelope.message is None
                else redact_token(envelope.message, self._token)
            ),
        )

    def _http_error(self, status_code: int, endpoint: str):
        if status_code in {401, 403}:
            return JustOneApiCredentialError(
                "provider rejected credentials",
                endpoint=endpoint,
                http_status=status_code,
            )
        if status_code == 429:
            return JustOneApiRateLimitError(
                "provider rate limit reached",
                endpoint=endpoint,
                http_status=status_code,
                retry_after_seconds=60.0,
            )
        if status_code == 400:
            return JustOneApiInvalidRequestError(
                "provider rejected request parameters",
                endpoint=endpoint,
                http_status=status_code,
            )
        if status_code >= 500:
            return JustOneApiHttpError(
                "provider returned an HTTP server error",
                endpoint=endpoint,
                http_status=status_code,
            )
        return JustOneApiProtocolError(
            f"unexpected HTTP status {status_code}",
            endpoint=endpoint,
            http_status=status_code,
        )

    async def _observe_failure(
        self,
        observer: Optional[RequestObserver],
        endpoint: str,
        duration_ms: int,
        attempt: int,
        error_type: str,
        *,
        http_status: Optional[int] = None,
        outcome_unknown: bool = False,
    ) -> None:
        await self._notify(
            observer,
            RequestRecord(
                endpoint=endpoint,
                request_id=None,
                http_status=http_status,
                business_code=None,
                duration_ms=duration_ms,
                attempt=attempt,
                billed=False,
                error_type=error_type,
                outcome_unknown=outcome_unknown,
            ),
        )

    async def _retry_sleep(self, attempt: int) -> None:
        delay = self._retry_base_sec * (2 ** max(0, attempt - 1))
        if delay > 0:
            await self._sleep(delay)

    @staticmethod
    async def _notify(callback, *args) -> None:
        if callback is None:
            return
        result = callback(*args)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, int((perf_counter() - started) * 1000))
