from .. import service_db

AccountStatus = getattr(service_db, "AccountStatus", None)


class AccountRepository:
    AccountStatus = AccountStatus

    async def get_active_accounts(self, *args, **kwargs):
        return await service_db.get_active_accounts(*args, **kwargs)

    async def update_account(self, *args, **kwargs):
        return await service_db.update_account(*args, **kwargs)

    async def get_account(self, *args, **kwargs):
        return await service_db.get_account(*args, **kwargs)

    async def get_proxy_profile(self, *args, **kwargs):
        return await service_db.get_proxy_profile(*args, **kwargs)

    async def list_accounts(self, *args, **kwargs):
        return await service_db.list_accounts(*args, **kwargs)

    async def add_account(self, *args, **kwargs):
        return await service_db.add_account(*args, **kwargs)

    async def delete_account(self, *args, **kwargs):
        return await service_db.delete_account(*args, **kwargs)

    async def list_candidate_accounts(self, *args, **kwargs):
        return await service_db.list_candidate_accounts(*args, **kwargs)

    async def upsert_candidate_account(self, *args, **kwargs):
        return await service_db.upsert_candidate_account(*args, **kwargs)

    async def delete_candidate_account(self, *args, **kwargs):
        return await service_db.delete_candidate_account(*args, **kwargs)
