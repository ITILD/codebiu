from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_site.do.todolist import Todolist, TodolistCreate, TodolistUpdate


class TodolistDao:
    """备忘数据访问(按 user_id 归属隔离; 存量 NULL 数据仅管理员可见)"""

    @DaoRel
    async def add(
        self, todolist: TodolistCreate, user_id: str, session: AsyncSession | None = None
    ) -> str:
        """新增备忘记录
        :param todolist: 备忘创建数据
        :param user_id: 归属用户ID
        :return: 新创建备忘ID
        """
        db_todolist = Todolist.model_validate(
            todolist.model_dump(exclude_unset=True), update={"user_id": user_id}
        )
        session.add(db_todolist)
        await session.flush()
        return db_todolist.id

    @DaoRel
    async def get(
        self, todolist_id: str, session: AsyncSession | None = None
    ) -> Todolist | None:
        """查询单个备忘(不限归属, 由服务层判定可见性)"""
        return await session.get(Todolist, todolist_id)

    @DaoRel
    async def update(
        self,
        todolist_id: str,
        todolist: TodolistUpdate,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """直接更新本人备忘记录(不先查询)
        :raises: ValueError 备忘不存在或不属于当前用户
        """
        update_data = todolist.model_dump(exclude_unset=True)
        stmt = (
            update(Todolist)
            .where(Todolist.id == todolist_id, Todolist.user_id == user_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {todolist_id} 的备忘")
        await session.flush()

    @DaoRel
    async def delete(
        self, todolist_id: str, user_id: str, session: AsyncSession | None = None
    ) -> None:
        """删除本人备忘
        :raises: ValueError 备忘不存在或不属于当前用户
        """
        todolist = await session.get(Todolist, todolist_id)
        if not todolist or (todolist.user_id and todolist.user_id != user_id):
            raise ValueError(f"未找到ID为 {todolist_id} 的备忘")
        await session.delete(todolist)
        await session.flush()

    @DaoRel
    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        session: AsyncSession | None = None,
        name: str | None = None,
        status: str | None = None,
    ) -> list[Todolist]:
        """分页查询本人备忘列表(支持名称模糊/状态过滤)"""
        conditions = [Todolist.user_id == user_id]
        if name:
            conditions.append(Todolist.name.contains(name))
        if status:
            conditions.append(Todolist.status == status)

        statement = (
            select(Todolist)
            .where(*conditions)
            .order_by(Todolist.start_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_mine(
        self,
        user_id: str,
        session: AsyncSession | None = None,
        name: str | None = None,
        status: str | None = None,
    ) -> int:
        """统计本人备忘总数(与列表过滤条件一致)"""
        conditions = [Todolist.user_id == user_id]
        if name:
            conditions.append(Todolist.name.contains(name))
        if status:
            conditions.append(Todolist.status == status)
        statement = select(func.count()).select_from(Todolist).where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def list_in_range(
        self,
        user_id: str,
        start: datetime,
        end: datetime,
        session: AsyncSession | None = None,
    ) -> list[Todolist]:
        """查询时间范围内的本人备忘(日历 年/月/周 视图数据源)
        :param start: 范围起始(含), 前端传本地日历起点(带时区)
        :param end: 范围结束(不含)
        """
        statement = (
            select(Todolist)
            .where(
                Todolist.user_id == user_id,
                Todolist.start_at >= start,
                Todolist.start_at < end,
            )
            .order_by(Todolist.start_at.asc())
        )
        result = await session.exec(statement)
        return result.all()
