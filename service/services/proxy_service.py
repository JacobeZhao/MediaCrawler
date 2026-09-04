from datetime import datetime

import httpx
from fastapi import HTTPException
from tools.redaction import redact_sensitive_text

from ..proxy_config import build_proxy_url, mask_proxy_url, normalize_proxy_server
from ..repositories.proxies import ProxyRepository
from ..schemas.proxies import ProxyProfileRequest, ProxyProfileUpdateRequest


class ProxyService:
    _CHECK_URL = "https://api.ipify.org?format=json"

    def __init__(self, repository: ProxyRepository | None = None):
        self._repository = repository if repository is not None else ProxyRepository()

    async def list_proxies(self):
        profiles = await self._repository.list_proxy_profiles(include_secret=False)
        return [self._public_profile(p) for p in profiles]

    async def create_proxy(self, req: ProxyProfileRequest):
        data = req.model_dump()
        try:
            data["server"] = normalize_proxy_server(data["server"], data["proxy_type"])
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        try:
            proxy_id = await self._repository.add_proxy_profile(data)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        profile = await self._repository.get_proxy_profile(proxy_id, include_secret=False)
        return {"proxy_id": proxy_id, "proxy": self._public_profile(profile), "message": "Proxy profile created."}

    async def update_proxy(self, proxy_id: int, req: ProxyProfileUpdateRequest):
        profile = await self._repository.get_proxy_profile(proxy_id, include_secret=False)
        if not profile:
            raise HTTPException(404, "Proxy profile not found.")
        data = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}
        if "server" in data:
            try:
                data["server"] = normalize_proxy_server(data["server"], data.get("proxy_type") or profile["proxy_type"])
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        try:
            await self._repository.update_proxy_profile(proxy_id, **data)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        updated = await self._repository.get_proxy_profile(proxy_id, include_secret=False)
        return {"proxy": self._public_profile(updated), "message": "Proxy profile updated."}

    async def delete_proxy(self, proxy_id: int):
        try:
            await self._repository.delete_proxy_profile(proxy_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"message": "Proxy profile deleted."}

    async def check_proxy(self, proxy_id: int):
        profile = await self._repository.get_proxy_profile(proxy_id, include_secret=True)
        if not profile:
            raise HTTPException(404, "Proxy profile not found.")
        try:
            proxy_url = build_proxy_url(profile)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not proxy_url:
            raise HTTPException(400, "Proxy profile is incomplete.")
        ok = False
        error = ""
        observed_ip = ""
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=20) as client:
                response = await client.get(self._CHECK_URL)
                response.raise_for_status()
                payload = response.json()
                observed_ip = str(payload.get("ip", ""))
                ok = bool(observed_ip)
        except Exception as exc:
            error = f"{type(exc).__name__}: {redact_sensitive_text(exc)}"
        await self._repository.update_proxy_profile(
            proxy_id,
            last_checked=datetime.now().isoformat(),
            last_error="" if ok else error[:500],
        )
        return {
            "ok": ok,
            "observed_ip": observed_ip,
            "message": "Proxy check passed." if ok else "Proxy check failed.",
            "error": "" if ok else error,
        }

    def _public_profile(self, profile):
        if not profile:
            return None
        public = dict(profile)
        public.pop("password", None)
        public["has_auth"] = bool(profile.get("username") or profile.get("has_password"))
        public["masked_url"] = mask_proxy_url(profile)
        return public
