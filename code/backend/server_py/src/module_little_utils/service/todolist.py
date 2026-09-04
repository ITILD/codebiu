# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_little_utils.do.todolist import Todolist, TodolistCreate, TodolistUpdate
from module_little_utils.dao.todolist import TodolistDao

# lib
# from config.db import async_transaction


class TodolistService:
    """todolist"""

    def __init__(self, todolist_dao: TodolistDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.todolist_dao = todolist_dao or TodolistDao()

    async def add(self, todolist: TodolistCreate) -> str:
        """新增计划任务

        :param todolist: 计划任务创建数据
        :return: 新建计划任务的ID
        """
        return await self.todolist_dao.add(todolist)

    async def delete(self, id: str):
        """删除指定计划任务

        :param id: 计划任务ID
        """
        await self.todolist_dao.delete(id)

    async def update(self,todolist_id: str, todolist: TodolistUpdate):
        """更新指定计划任务

        :param todolist_id: 计划任务ID
        :param todolist: 计划任务更新数据
        """
        await self.todolist_dao.update(todolist_id,todolist)

    async def get(self, id: str) -> Todolist | None:
        """查询单个计划任务

        :param id: 计划任务ID
        :return: 计划任务对象,未找到返回None
        """
        return await self.todolist_dao.get(id)
    # 
    async def list_paged(
        self,
        pagination: PaginationParams,
        name: str | None = None,
        status: str | None = None,
    ):
        """
        分页获取计划任务列表(支持多字段过滤)
        :param pagination: 分页参数
        :param name: 计划任务名称模糊匹配
        :param status: 代办状态精确过滤(todo/done)
        """
        items = await self.todolist_dao.list_paged(pagination, name=name, status=status)
        total = await self.todolist_dao.count(name=name, status=status)
        return PaginationResponse.create(items, total,pagination)
    async def get_scroll(self, params: InfiniteScrollParams):
        """滚动加载计划任务列表(无限滚动场景)

        :param params: 滚动分页参数
        :return: 滚动分页响应(含数据与下一页游标)
        """
        items:list[Todolist] = await self.todolist_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)