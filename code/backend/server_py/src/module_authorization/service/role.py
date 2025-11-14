from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.role import Role, RoleCreate, RoleUpdate, RoleResponse
from module_authorization.dao.role import RoleDao


class RoleService:
    """角色服务"""

    def __init__(self, role_dao: RoleDao):
        self.role_dao = role_dao

    async def add(self, role: RoleCreate):
        """
        创建角色
        :param role: 角色创建数据
        :return: 创建的角色ID
        """
        return await self.role_dao.add(role)

    async def delete(self, role_id: str):
        """
        删除角色
        :param role_id: 角色ID
        """
        await self.role_dao.delete(role_id)

    async def update(self, role_id: str, role: RoleUpdate):
        """
        更新角色
        :param role_id: 角色ID
        :param role: 角色更新数据
        """
        await self.role_dao.update(role_id, role)

    async def get(self, role_id: str) -> Role | None:
        """
        获取角色详情
        :param role_id: 角色ID
        :return: 角色对象
        """
        return await self.role_dao.get(role_id)

    async def get_by_name(self, name: str) -> Role | None:
        """
        根据角色名称获取角色
        :param name: 角色名称
        :return: 角色对象
        """
        return await self.role_dao.get_by_name(name)

    async def list(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页获取角色列表
        :param pagination: 分页参数
        :return: 分页角色列表
        """
        items = await self.role_dao.list(pagination)
        total = await self.role_dao.count()
        return PaginationResponse.create(items, total, pagination)