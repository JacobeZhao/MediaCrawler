from typing import Dict, Optional
from urllib.parse import quote, urlparse

_SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5"}


def _validate_proxy_server_url(server: str) -> str:
    parsed = urlparse(server)
    if parsed.scheme not in _SUPPORTED_PROXY_SCHEMES:
        raise ValueError("Unsupported proxy type.")
    if parsed.username or parsed.password:
        raise ValueError("Proxy credentials must be stored in username/password fields, not in server.")
    if not parsed.hostname:
        raise ValueError("Proxy server must include a host.")
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Proxy server must not include path, query, or fragment.")
    return parsed.geturl()


def normalize_proxy_server(server: str, proxy_type: str = "http") -> str:
    raw = (server or "").strip()
    if not raw:
        return ""
    if "://" in raw:
        return _validate_proxy_server_url(raw)
    scheme = (proxy_type or "http").strip().lower() or "http"
    return _validate_proxy_server_url(f"{scheme}://{raw}")


def _redact_server_auth(server: str) -> str:
    parsed = urlparse(server)
    if not parsed.scheme or not parsed.netloc:
        return server
    if not (parsed.username or parsed.password):
        return parsed.geturl()
    host = parsed.netloc.rsplit("@", 1)[-1]
    return parsed._replace(netloc=f"***:***@{host}").geturl()


def build_proxy_url(profile: Optional[Dict]) -> Optional[str]:
    if not profile:
        return None
    server = normalize_proxy_server(profile.get("server", ""), profile.get("proxy_type", "http"))
    if not server:
        return None
    username = profile.get("username") or ""
    password = profile.get("password") or ""
    if not username:
        return server

    parsed = urlparse(server)
    if not parsed.scheme or not parsed.netloc:
        return server
    auth = quote(username, safe="")
    if password:
        auth = f"{auth}:{quote(password, safe='')}"
    return parsed._replace(netloc=f"{auth}@{parsed.netloc}").geturl()


def build_playwright_proxy(profile: Optional[Dict]) -> Optional[Dict[str, str]]:
    if not profile:
        return None
    server = normalize_proxy_server(profile.get("server", ""), profile.get("proxy_type", "http"))
    if not server:
        return None
    proxy = {"server": server}
    if profile.get("username"):
        proxy["username"] = profile["username"]
    if profile.get("password"):
        proxy["password"] = profile["password"]
    return proxy


def mask_proxy_url(profile: Optional[Dict]) -> str:
    if not profile:
        return ""
    try:
        server = normalize_proxy_server(profile.get("server", ""), profile.get("proxy_type", "http"))
    except ValueError:
        return _redact_server_auth(profile.get("server", ""))
    if not server:
        return ""
    parsed = urlparse(server)
    if not parsed.scheme or not parsed.netloc:
        return server
    if parsed.username or parsed.password:
        return _redact_server_auth(server)
    username = profile.get("username") or ""
    if username:
        return parsed._replace(netloc=f"{username}:***@{parsed.netloc}").geturl()
    return parsed.geturl()
