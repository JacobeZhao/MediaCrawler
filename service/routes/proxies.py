from fastapi import APIRouter

from ..dependencies import get_proxy_service
from ..schemas.proxies import ProxyProfileRequest, ProxyProfileUpdateRequest

router = APIRouter(prefix="/api/proxies")


@router.get("")
async def list_proxies():
    return await get_proxy_service().list_proxies()


@router.post("")
async def create_proxy(req: ProxyProfileRequest):
    return await get_proxy_service().create_proxy(req)


@router.patch("/{proxy_id}")
async def update_proxy(proxy_id: int, req: ProxyProfileUpdateRequest):
    return await get_proxy_service().update_proxy(proxy_id, req)


@router.delete("/{proxy_id}")
async def delete_proxy(proxy_id: int):
    return await get_proxy_service().delete_proxy(proxy_id)


@router.post("/{proxy_id}/check")
async def check_proxy(proxy_id: int):
    return await get_proxy_service().check_proxy(proxy_id)
