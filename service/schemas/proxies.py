from typing import Optional

from pydantic import BaseModel, Field


class ProxyProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    proxy_type: str = Field(default="http", pattern="^(http|https|socks5)$")
    server: str = Field(min_length=1, max_length=500)
    username: str = Field(default="", max_length=255)
    password: str = Field(default="", max_length=255)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class ProxyProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    proxy_type: Optional[str] = Field(default=None, pattern="^(http|https|socks5)$")
    server: Optional[str] = Field(default=None, min_length=1, max_length=500)
    username: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, pattern="^(active|inactive)$")
