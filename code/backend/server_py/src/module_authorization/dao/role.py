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
        直接更新角色记录（不先查询）
        :param role_id: 要更新的角色ID
        :param role: 角色更新数据
        :param session: 可选数据库会话
        :return: 更新成功的角色ID
        :raises: ValueError 如果角色不存在
        """
        # 准备更新数据（排除未设置的字段）
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
        """
        根据角色名称查询角色
        :param name: 角色名称
        :param session: 可选数据库会话
        :return: 角色对象，未找到返回None
        """
        stmt = select(Role).where(Role.name == name)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ):
        """
        分页查询角色列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 角色列表
        """
        statement = select(Role).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None):
        """
        获取角色总数
        :param session: 可选数据库会话
        :return: 角色总数
        """
        statement = select(func.count()).select_from(Role)
        result = await session.exec(statement)
        return result.one()