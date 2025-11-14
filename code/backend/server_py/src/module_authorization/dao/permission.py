from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    PaginationParams,
)
from common.config.db import DaoRel
from module_authorization.do.permission import Permission, PermissionCreate, PermissionUpdate


class PermissionDao:
    @DaoRel
    async def add(
        self, permission: PermissionCreate, session: AsyncSession | None = None
    ):
        """
        新增权限记录
        :param permission: 权限创建数据
        :param session: 可选数据库会话
        :return: 新创建权限的ID
        """
        db_permission = Permission.model_validate(permission.model_dump(exclude_unset=True))
        session.add(db_permission)
        await session.flush()
        return db_permission.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None):
        """
        删除权限记录
        :param id: 要删除的权限ID
        :param session: 可选数据库会话
        """
        permission = await session.get(Permission, id)
        if not permission:
            raise ValueError(f"未找到ID为 {id} 的权限")
        await session.delete(permission)
        await session.flush()

    @DaoRel
    async def update(
        self,
        permission_id: str,
        permission: PermissionUpdate,
        session: AsyncSession | None = None,
    ):
        """
        直接更新权限记录（不先查询）
        :param permission_id: 要更新的权限ID
        :param permission: 权限更新数据
        :param session: 可选数据库会话
        :return: 更新成功的权限ID
        :raises: ValueError 如果权限不存在
        """
        # 准备更新数据（排除未设置的字段）
        update_data = permission.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(Permission).where(Permission.id == permission_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {permission_id} 的权限")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None):
        """
        查询单个权限
        :param id: 要查询的权限ID
        :param session: 可选数据库会话
        :return: 权限对象，未找到返回None
        """
        return await session.get(Permission, id)

    @DaoRel
    async def get_by_code(self, code, session: AsyncSession | None = None):
        """
        根据权限代码查询权限
        :param code: 权限代码
        :param session: 可选数据库会话
        :return: 权限对象，未找到返回None
        """
        stmt = select(Permission).where(Permission.code == code)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ):
        """
        分页查询权限列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 权限列表
        """
        statement = select(Permission).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None):
        """
        获取权限总数
        :param session: 可选数据库会话
        :return: 权限总数
        """
        statement = select(func.count()).select_from(Permission)
        result = await session.exec(statement)
        return result.one()