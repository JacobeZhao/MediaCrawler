from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEYS = (
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "cookie_json",
    "cookie",
    "customer-sso-sid",
    "id_token",
    "password",
    "proxy_password",
    "session",
    "token",
    "web_session",
    "xsec_token",
    "a1",
)
_KEY_PATTERN = "|".join(re.escape(key) for key in _SENSITIVE_KEYS)
_QUERY_VALUE_RE = re.compile(
    rf"(?i)(\b(?:{_KEY_PATTERN})\s*=\s*)([^&\s,;\"']+)"
)
_QUOTED_VALUE_RE = re.compile(
    rf"(?i)([\"'](?:{_KEY_PATTERN})[\"']\s*:\s*)([\"'])(.*?)(\2)"
)
_AUTHORIZATION_HEADER_RE = re.compile(r"(?im)(\bauthorization\s*:\s*)([^\r\n,]+)")
_COOKIE_HEADER_RE = re.compile(r"(?im)(\bcookie\s*:\s*)([^\r\n]+)")
_URL_USERINFO_RE = re.compile(r"(?i)(https?://)([^/@\s:]+):([^/@\s]+)@")


def redact_sensitive_text(value: Any, *, max_length: int = 2000) -> str:
    """Return bounded diagnostic text with common credential fields removed."""
    text = str(value)
    text = _QUOTED_VALUE_RE.sub(r"\1\2<redacted>\2", text)
    text = _QUERY_VALUE_RE.sub(r"\1<redacted>", text)
    text = _AUTHORIZATION_HEADER_RE.sub(r"\1<redacted>", text)
    text = _COOKIE_HEADER_RE.sub(r"\1<redacted>", text)
    text = _URL_USERINFO_RE.sub(r"\1<redacted>:<redacted>@", text)
    if max_length >= 0 and len(text) > max_length:
        return f"{text[:max_length]}...<truncated>"
    return text
