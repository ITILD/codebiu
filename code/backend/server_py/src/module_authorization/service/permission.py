from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.permission import Permission, PermissionCreate, PermissionUpdate, PermissionResponse
from module_authorization.dao.permission import PermissionDao


class PermissionService:
    """权限服务"""

    def __init__(self, permission_dao: PermissionDao):
        self.permission_dao = permission_dao

    async def add(self, permission: PermissionCreate):
        """
        创建权限
        :param permission: 权限创建数据
        :return: 创建的权限ID
        """
        return await self.permission_dao.add(permission)

    async def delete(self, permission_id: str):
        """
        删除权限
        :param permission_id: 权限ID
        """
        await self.permission_dao.delete(permission_id)

    async def update(self, permission_id: str, permission: PermissionUpdate):
        """
        更新权限
        :param permission_id: 权限ID
        :param permission: 权限更新数据
        """
        await self.permission_dao.update(permission_id, permission)

    async def get(self, permission_id: str) -> Permission | None:
        """
        获取权限详情
        :param permission_id: 权限ID
        :return: 权限对象
        """
        return await self.permission_dao.get(permission_id)

    async def get_by_code(self, code: str) -> Permission | None:
        """
        根据权限代码获取权限
        :param code: 权限代码
        :return: 权限对象
        """
        return await self.permission_dao.get_by_code(code)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页获取权限列表
        :param pagination: 分页参数
        :return: 分页权限列表
        """
        items = await self.permission_dao.list_all(pagination)
        total = await self.permission_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_permissions_by_parent_id(self, parent_id: str) -> list:
        """
        获取指定父权限下的所有子权限
        :param parent_id: 父权限ID
        :return: 权限列表
        """
        # 注意：这里需要实现通过父ID查询权限的功能
        # 由于当前DAO没有此方法，实际项目中需要在PermissionDao中添加相应方法
        raise NotImplementedError("获取子权限功能尚未实现")