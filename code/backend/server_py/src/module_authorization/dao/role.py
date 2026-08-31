from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    PaginationParams,
)
from common.config.db import DaoRel
from module_authorization.do.role import Role, RoleCreate, RoleUpdate


class RoleDao:
    @DaoRel
    async def add(
        self, role: RoleCreate, session: AsyncSession | None = None
    ):
        """
        新增角色记录
        :param role: 角色创建数据
        :param session: 可选数据库会话
        :return: 新创建角色的ID
        """
        db_role = Role.model_validate(role.model_dump(exclude_unset=True))
        session.add(db_role)
        await session.flush()
        return db_role.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None):
        """
        删除角色记录
        :param id: 要删除的角色ID
        :param session: 可选数据库会话
        """
        role = await session.get(Role, id)
        if not role:
            raise ValueError(f"未找到ID为 {id} 的角色")
        await session.delete(role)
        await session.flush()

    @DaoRel
    async def update(
        self,
        role_id: str,
        role: RoleUpdate,
        session: AsyncSession | None = None,
    ):
        """
        直接更新角色记录(不先查询)
        :param role_id: 要更新的角色ID
        :param role: 角色更新数据
        :param session: 可选数据库会话
        :return: 更新成功的角色ID
        :raises: ValueError 如果角色不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = role.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(Role).where(Role.id == role_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {role_id} 的角色")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None):
        """
        查询单个角色
        :param id: 要查询的角色ID
        :param session: 可选数据库会话
        :return: 角色对象，未找到返回None
        """
        return await session.get(Role, id)

    @DaoRel
    async def get_by_name(self, name, session: AsyncSession | None = None):
        """根据角色名称查询角色"""
        stmt = select(Role).where(Role.name == name)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def get_by_role_key(self, role_key: str, session: AsyncSession | None = None):
        """根据角色权限字符串查询角色"""
        stmt = select(Role).where(Role.role_key == role_key)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list_all_no_page(self, session: AsyncSession | None = None) -> list[Role]:
        """查询所有角色(不分页)"""
        statement = select(Role).order_by(Role.sort)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def list_all(
        self,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
        name: str | None = None,
        role_key: str | None = None,
        is_active: bool | None = None,
    ):
        """
        分页查询角色列表(支持多字段过滤)
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param name: 角色名称模糊匹配
        :param role_key: 权限字符模糊匹配
        :param is_active: 状态精确过滤(启用/禁用)
        :return: 角色列表
        """
        conditions = []
        if name:
            conditions.append(Role.name.contains(name))
        if role_key:
            conditions.append(Role.role_key.contains(role_key))
        if is_active is not None:
            conditions.append(Role.is_active == is_active)

        statement = select(Role)
        if conditions:
            statement = statement.where(*conditions)
        statement = statement.offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(
        self,
        session: AsyncSession | None = None,
        name: str | None = None,
        role_key: str | None = None,
        is_active: bool | None = None,
    ):
        """
        获取角色总数(与列表过滤条件保持一致)
        :param session: 可选数据库会话
        :param name: 角色名称模糊匹配
        :param role_key: 权限字符模糊匹配
        :param is_active: 状态精确过滤(启用/禁用)
        :return: 角色总数
        """
        conditions = []
        if name:
            conditions.append(Role.name.contains(name))
        if role_key:
            conditions.append(Role.role_key.contains(role_key))
        if is_active is not None:
            conditions.append(Role.is_active == is_active)

        statement = select(func.count()).select_from(Role)
        if conditions:
            statement = statement.where(*conditions)
        result = await session.exec(statement)
        return result.one()