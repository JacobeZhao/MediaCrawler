# -*- coding: utf-8 -*-
import httpx
import config


def make_async_client(**kwargs) -> httpx.AsyncClient:
    """创建统一配置的 httpx.AsyncClient。

    从配置文件读取 DISABLE_SSL_VERIFY（默认 False，即开启 SSL 验证）。
    Set to True only when a local TLS interception tool requires it.
    """
    kwargs.setdefault("verify", not getattr(config, "DISABLE_SSL_VERIFY", False))
    return httpx.AsyncClient(**kwargs)
