from datetime import datetime

from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_site.do.todolist import Todolist, TodolistCreate, TodolistUpdate
from module_site.dao.todolist import TodolistDao


class TodolistService:
    """备忘服务: 编辑管理 + 日历展示数据源"""

    def __init__(self, todolist_dao: TodolistDao):
        """依赖注入构造器: 初始化所需的数据访问对象"""
        self.todolist_dao = todolist_dao

    async def add(self, todolist: TodolistCreate, user_id: str) -> str:
        """新增备忘(归属当前用户)
        :return: 新建备忘ID
        """
        return await self.todolist_dao.add(todolist, user_id)

    async def update(self, todolist_id: str, todolist: TodolistUpdate, user_id: str) -> None:
        """更新本人备忘"""
        await self.todolist_dao.update(todolist_id, todolist, user_id)

    async def delete(self, todolist_id: str, user_id: str) -> None:
        """删除本人备忘"""
        await self.todolist_dao.delete(todolist_id, user_id)

    async def get(self, todolist_id: str, user_id: str) -> Todolist | None:
        """查询单个备忘(仅本人可见)"""
        result = await self.todolist_dao.get(todolist_id)
        if result and result.user_id and result.user_id != user_id:
            return None
        return result

    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        name: str | None = None,
        status: str | None = None,
    ) -> PaginationResponse:
        """分页获取本人备忘列表(管理页)"""
        items = await self.todolist_dao.list_mine(
            pagination, user_id, name=name, status=status
        )
        total = await self.todolist_dao.count_mine(user_id, name=name, status=status)
        return PaginationResponse.create(items, total, pagination)

    async def list_in_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> list[Todolist]:
        """获取时间范围内的本人备忘(日历 年/月/周 视图数据源)"""
        return await self.todolist_dao.list_in_range(user_id, start, end)
