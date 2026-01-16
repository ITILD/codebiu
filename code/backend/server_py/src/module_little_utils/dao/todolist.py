from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_little_utils.do.todolist import Todolist, TodolistCreate, TodolistUpdate


class TodolistDao:
    @DaoRel
    async def add(
        self, todolist: TodolistCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增计划列表记录
        :param todolist: 计划列表创建数据
        :param session: 可选数据库会话
        :return: 新创建计划列表的ID
        """
        db_todolist = Todolist.model_validate(todolist.model_dump(exclude_unset=True))
        session.add(db_todolist)
        await session.flush()
        return db_todolist.id

    # refresh会丢弃本身
    # 是直接refresh还是再次查询自己需要的字段 只要id？
    # refresh(attribute_names=["title"])
    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None) -> str:
        """
        删除计划列表记录
        :param id: 要删除的计划列表ID
        :param session: 可选数据库会话
        """
        todolist = await session.get(Todolist, id)
        if not todolist:
            raise ValueError(f"未找到ID为 {id} 的计划列表")
        await session.delete(todolist)
        await session.flush()

    @DaoRel
    async def update(
        self,
        todolist_id: str,
        todolist: TodolistUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        直接更新计划列表记录(不先查询)
        :param todolist_id: 要更新的计划列表ID
        :param todolist: 计划列表更新数据
        :param session: 可选数据库会话
        :return: 更新成功的计划列表ID
        :raises: ValueError 如果计划列表不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = todolist.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(Todolist).where(Todolist.id == todolist_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {todolist_id} 的计划列表")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None) -> str:
        """
        查询单个计划列表
        :param id: 要查询的计划列表ID
        :param session: 可选数据库会话
        :return: 计划列表对象，未找到返回None
        """
        return await session.get(Todolist, id)

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[Todolist]:
        """
        分页查询计划列表列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 计划列表列表
        """
        statement = select(Todolist).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list[Todolist]:
        """
        无限滚动分页查询  先查询最新的 滚下拉更早的
        :param last_id: 最后收到的计划列表ID(None表示第一页)
        :param limit: 每页最大记录数
        :param session: 可选数据库会话
        :return: 计划列表列表
        """
        # 返回类型
        statement = select(Todolist)
        # 设置默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"
        # 根据游标
        if params.last_id:
            last_todolist = await session.get(Todolist, params.last_id)
            if not last_todolist:
                raise ValueError(f"未找到ID为 {params.last_id} 的计划列表")

            # 获取排序字段的值
            sort_value = getattr(last_todolist, sort_by)
            search_value = getattr(Todolist, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)
        # 正反排序
        order = None
        if params.direction == ScrollDirection.UP:
            # 升序：从小到大，从早到晚
            order = getattr(Todolist, sort_by).asc()
        else:
            order = getattr(Todolist, sort_by).desc()
        statement = statement.order_by(order)
        # 限制结果数量  实际查询 limit + 1 条
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计计划列表总数
        :param session: 可选数据库会话
        :return: 计划列表总数量
        """
        statement = select(func.count()).select_from(Todolist)
        result = await session.exec(statement)
        return result.one()
