from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Type

from .models import ApiEnvelope


class JustOneApiError(Exception):
    category = "provider_error"
    retryable = False
    pauses_provider = False

    def __init__(
        self,
        message: str,
        *,
        code: Optional[int] = None,
        request_id: Optional[str] = None,
        endpoint: str = "",
        http_status: Optional[int] = None,
        retry_after_seconds: Optional[float] = None,
    ):
        self.message = message
        self.code = code
        self.request_id = request_id
        self.endpoint = endpoint
        self.http_status = http_status
        self.retry_after_seconds = retry_after_seconds
        details = [self.category]
        if code is not None:
            details.append(f"code={code}")
        if request_id:
            details.append(f"request_id={request_id}")
        if endpoint:
            details.append(f"endpoint={endpoint}")
        super().__init__(f"JustOneAPI {' '.join(details)}: {message}")


class JustOneApiCredentialError(JustOneApiError):
    category = "credential"
    pauses_provider = True


class JustOneApiUpstreamError(JustOneApiError):
    category = "upstream"
    retryable = True


class JustOneApiRateLimitError(JustOneApiError):
    category = "rate_limit"


class JustOneApiDailyQuotaError(JustOneApiError):
    category = "daily_quota"
    pauses_provider = True


class JustOneApiInvalidRequestError(JustOneApiError):
    category = "invalid_request"


class JustOneApiBalanceError(JustOneApiError):
    category = "insufficient_balance"
    pauses_provider = True


class JustOneApiTokenLimitError(JustOneApiError):
    category = "token_limit"
    pauses_provider = True


class JustOneApiHttpError(JustOneApiError):
    category = "http_error"


class JustOneApiTransportError(JustOneApiError):
    category = "transport"
    retryable = True


class JustOneApiUnknownOutcomeError(JustOneApiError):
    category = "unknown_outcome"


class JustOneApiProtocolError(JustOneApiError):
    category = "invalid_response"


_BUSINESS_ERRORS: dict[int, Type[JustOneApiError]] = {
    100: JustOneApiCredentialError,
    301: JustOneApiUpstreamError,
    302: JustOneApiRateLimitError,
    303: JustOneApiDailyQuotaError,
    400: JustOneApiInvalidRequestError,
    500: JustOneApiUpstreamError,
    600: JustOneApiCredentialError,
    601: JustOneApiBalanceError,
    602: JustOneApiTokenLimitError,
}


def seconds_until_shanghai_midnight(now: Optional[datetime] = None) -> float:
    shanghai_timezone = timezone(timedelta(hours=8))
    current = (
        now.astimezone(shanghai_timezone)
        if now is not None
        else datetime.now(shanghai_timezone)
    )
    tomorrow = (current + timedelta(days=1)).date()
    midnight = datetime.combine(
        tomorrow,
        datetime.min.time(),
        tzinfo=shanghai_timezone,
    )
    return max(1.0, (midnight - current).total_seconds())


def error_from_envelope(envelope: ApiEnvelope) -> JustOneApiError:
    error_type = _BUSINESS_ERRORS.get(envelope.code, JustOneApiError)
    retry_after = None
    if envelope.code == 302:
        retry_after = 60.0
    elif envelope.code == 303:
        retry_after = seconds_until_shanghai_midnight()
    return error_type(
        envelope.message or "request rejected",
        code=envelope.code,
        request_id=envelope.request_id,
        endpoint=envelope.endpoint,
        http_status=envelope.http_status,
        retry_after_seconds=retry_after,
    )
