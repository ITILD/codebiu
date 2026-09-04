from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_main.do.dict_item import DictItem, DictItemCreate, DictItemUpdate
from module_main.dao.dict_item import DictItemDao
from module_main.dao.dict_type import DictTypeDao


class DictItemService:
    """字典项服务"""

    def __init__(self, dict_item_dao: DictItemDao, dict_type_dao: DictTypeDao):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.dict_item_dao = dict_item_dao or DictItemDao()
        self.dict_type_dao = dict_type_dao or DictTypeDao()

    async def add(self, dict_item: DictItemCreate) -> str:
        """新增字典项"""
        return await self.dict_item_dao.add(dict_item)

    async def delete(self, id: str) -> None:
        """删除字典项"""
        await self.dict_item_dao.delete(id)

    async def update(self, dict_item_id: str, dict_item: DictItemUpdate) -> None:
        """更新字典项"""
        await self.dict_item_dao.update(dict_item_id, dict_item)

    async def get(self, id: str) -> DictItem | None:
        """获取单个字典项"""
        return await self.dict_item_dao.get(id)

    async def get_by_code(self, item_code: str) -> DictItem | None:
        """根据字典项编码全局获取字典项"""
        return await self.dict_item_dao.get_by_item_code(item_code)

    async def list_by_dict_type(self, type_code: str) -> list[DictItem]:
        """
        根据字典类型编码查询所有字典项
        先按编码查类型(拿到类型ID), 再按类型ID查字典项列表
        """
        dict_type = await self.dict_type_dao.get_by_code(type_code)
        if not dict_type:
            return []
        return await self.dict_item_dao.list_by_dict_type(dict_type.id)

    async def list_paged(self, pagination: PaginationParams) -> PaginationResponse:
        """分页查询字典项列表"""
        items = await self.dict_item_dao.list_paged(pagination)
        total = await self.dict_item_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """无限滚动查询字典项"""
        items: list[DictItem] = await self.dict_item_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def count_by_dict_type(self, type_code: str) -> int:
        """根据字典类型编码统计字典项数量(先按编码查类型, 再按类型ID统计)"""
        dict_type = await self.dict_type_dao.get_by_code(type_code)
        if not dict_type:
            return 0
        return await self.dict_item_dao.count_by_dict_type(dict_type.id)