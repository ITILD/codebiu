from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_authorization.do.role import Role, RoleCreate, RoleUpdate, RoleResponse
from module_authorization.dao.role import RoleDao


class RoleService:
    """角色服务"""

    def __init__(self, role_dao: RoleDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.role_dao = role_dao or RoleDao()

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
        """根据角色名称获取角色"""
        return await self.role_dao.get_by_name(name)

    async def get_by_role_key(self, role_key: str) -> Role | None:
        """根据角色权限字符串获取角色"""
        return await self.role_dao.get_by_role_key(role_key)

    async def list_all(self) -> list[Role]:
        """获取所有角色(不分页)"""
        return await self.role_dao.list_all()

    async def list_paged(
        self,
        pagination: PaginationParams,
        name: str | None = None,
        role_key: str | None = None,
        is_active: bool | None = None,
    ) -> PaginationResponse:
        """
        分页获取角色列表(支持多字段过滤)
        :param pagination: 分页参数
        :param name: 角色名称模糊匹配
        :param role_key: 权限字符模糊匹配
        :param is_active: 状态精确过滤(启用/禁用)
        """
        items = await self.role_dao.list_paged(
            pagination, name=name, role_key=role_key, is_active=is_active
        )
        total = await self.role_dao.count(
            name=name, role_key=role_key, is_active=is_active
        )
        return PaginationResponse.create(items, total, pagination)