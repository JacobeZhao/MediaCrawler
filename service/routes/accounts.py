from fastapi import APIRouter

from ..dependencies import get_account_service
from ..schemas.accounts import (
    AccountCookieRequest,
    AccountProxyRequest,
    AccountQrcodeStartRequest,
    AccountRequest,
    CandidateAccountBulkRequest,
)

router = APIRouter(prefix="/api/accounts")


@router.get("")
async def list_accounts():
    return await get_account_service().list_accounts()


@router.post("")
async def add_account(req: AccountRequest):
    return await get_account_service().add_account(req)


@router.get("/candidates")
async def list_candidate_accounts():
    return await get_account_service().list_candidate_accounts()


@router.post("/candidates")
async def save_candidate_accounts(req: CandidateAccountBulkRequest):
    return await get_account_service().save_candidate_accounts(req)


@router.delete("/candidates/{candidate_id}")
async def delete_candidate_account(candidate_id: int):
    return await get_account_service().delete_candidate_account(candidate_id)


@router.delete("/{account_id}")
async def delete_account(account_id: int):
    return await get_account_service().delete_account(account_id)


@router.post("/{account_id}/cookie")
async def update_account_cookie(account_id: int, req: AccountCookieRequest):
    return await get_account_service().update_account_cookie(account_id, req)


@router.post("/{account_id}/proxy")
async def update_account_proxy(account_id: int, req: AccountProxyRequest):
    return await get_account_service().update_account_proxy(account_id, req)


@router.post("/health_check")
async def health_check_accounts():
    return await get_account_service().health_check_accounts()


@router.post("/qrcode/start")
async def start_account_qrcode(req: AccountQrcodeStartRequest):
    return await get_account_service().start_qrcode(req)


@router.get("/qrcode/{session_id}/poll")
async def poll_account_qrcode(session_id: str):
    return await get_account_service().poll_qrcode(session_id)


@router.delete("/qrcode/{session_id}")
async def cancel_account_qrcode(session_id: str):
    return await get_account_service().cancel_qrcode(session_id)
