# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_little_utils.do.todolist import Todolist, TodolistCreate, TodolistUpdate
from module_little_utils.dao.todolist import TodolistDao

# lib
# from config.db import async_transaction


class TodolistService:
    """todolist"""

    def __init__(self, todolist_dao: TodolistDao):
        self.todolist_dao = todolist_dao or TodolistDao()

    async def add(self, todolist: TodolistCreate) -> str:
        return await self.todolist_dao.add(todolist)

    async def delete(self, id: str):
        await self.todolist_dao.delete(id)

    async def update(self,todolist_id: str, todolist: TodolistUpdate):
        await self.todolist_dao.update(todolist_id,todolist)

    async def get(self, id: str) -> Todolist | None:
        return await self.todolist_dao.get(id)
    # 
    async def list_all(self, pagination: PaginationParams):
        items = await self.todolist_dao.list_all(pagination)
        total = await self.todolist_dao.count()
        return PaginationResponse.create(items, total,pagination)
    async def get_scroll(self, params: InfiniteScrollParams):

        items:list[Todolist] = await self.todolist_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)