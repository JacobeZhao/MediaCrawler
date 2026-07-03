from typing import List, Optional

from pydantic import BaseModel, Field


class CookieRequest(BaseModel):
    cookie: str = Field(min_length=1, max_length=20000)


class AccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cookie: str = Field(min_length=1, max_length=20000)
    proxy_id: Optional[int] = Field(default=None, ge=1)


class AccountCookieRequest(BaseModel):
    cookie: str = Field(min_length=1, max_length=20000)


class AccountQrcodeStartRequest(BaseModel):
    name: str = Field(default="new-account", min_length=1, max_length=100)
    proxy_id: Optional[int] = Field(default=None, ge=1)


class CandidateAccountRequest(BaseModel):
    source: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=50)
    sms_link: str = Field(default="", max_length=1000)
    fm_link: str = Field(default="", max_length=1000)
    user_id: str = Field(default="", max_length=255)
    nickname: str = Field(default="", max_length=255)
    password: str = Field(default="", max_length=255)
    registered_at: str = Field(default="", max_length=50)
    cookie_json: str = Field(default="", max_length=50000)
    note: Optional[str] = Field(default="", max_length=1000)


class CandidateAccountBulkRequest(BaseModel):
    accounts: List[CandidateAccountRequest] = Field(min_length=1, max_length=200)


class AccountProxyRequest(BaseModel):
    proxy_id: Optional[int] = Field(default=None, ge=1)
    restart: bool = True
