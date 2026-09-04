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
        """新增权限记录"""
        db_permission = Permission.model_validate(permission.model_dump(exclude_unset=True))
        session.add(db_permission)
        await session.flush()
        return db_permission.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None):
        """删除权限记录"""
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
        """更新权限记录"""
        update_data = permission.model_dump(exclude_unset=True)
        stmt = update(Permission).where(Permission.id == permission_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {permission_id} 的权限")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None):
        """查询单个权限"""
        return await session.get(Permission, id)

    @DaoRel
    async def get_by_code(self, code, session: AsyncSession | None = None):
        """根据权限代码查询权限"""
        stmt = select(Permission).where(Permission.code == code)
        result = await session.exec(stmt)
        return result.first()

    @DaoRel
    async def list_paged(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ):
        """分页查询权限列表"""
        statement = select(Permission).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def list_all(self, session: AsyncSession | None = None) -> list[Permission]:
        """查询所有权限(不分页, 用于构建树)"""
        statement = select(Permission).order_by(Permission.order_num)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_by_parent_id(
        self, parent_id: str, session: AsyncSession | None = None
    ) -> list[Permission]:
        """根据父ID查询子权限"""
        statement = select(Permission).where(Permission.parent_id == parent_id).order_by(Permission.order_num)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None):
        """获取权限总数"""
        statement = select(func.count()).select_from(Permission)
        result = await session.exec(statement)
        return result.one()