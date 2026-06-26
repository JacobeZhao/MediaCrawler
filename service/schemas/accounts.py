from pydantic import BaseModel, Field


class CookieRequest(BaseModel):
    cookie: str = Field(min_length=1, max_length=20000)


class AccountRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cookie: str = Field(min_length=1, max_length=20000)


class AccountCookieRequest(BaseModel):
    cookie: str = Field(min_length=1, max_length=20000)


class AccountQrcodeStartRequest(BaseModel):
    name: str = Field(default="new-account", min_length=1, max_length=100)
