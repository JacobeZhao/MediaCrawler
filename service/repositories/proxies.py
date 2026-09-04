from .. import service_db


class ProxyRepository:
    async def list_proxy_profiles(self, *args, **kwargs):
        return await service_db.list_proxy_profiles(*args, **kwargs)

    async def get_proxy_profile(self, *args, **kwargs):
        return await service_db.get_proxy_profile(*args, **kwargs)

    async def add_proxy_profile(self, *args, **kwargs):
        return await service_db.add_proxy_profile(*args, **kwargs)

    async def update_proxy_profile(self, *args, **kwargs):
        return await service_db.update_proxy_profile(*args, **kwargs)

    async def delete_proxy_profile(self, *args, **kwargs):
        return await service_db.delete_proxy_profile(*args, **kwargs)
