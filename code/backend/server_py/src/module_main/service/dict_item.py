from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_main.do.dict_item import DictItem, DictItemCreate, DictItemUpdate
from module_main.dao.dict_item import DictItemDao


class DictItemService:
    """字典项服务"""

    def __init__(self, dict_item_dao: DictItemDao):
        self.dict_item_dao = dict_item_dao or DictItemDao()

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

    async def get_by_code(self, dict_type_id: str, item_code: str) -> DictItem | None:
        """根据字典类型ID和编码获取字典项"""
        return await self.dict_item_dao.get_by_code(dict_type_id, item_code)

    async def list_by_dict_type(self, dict_type_id: str) -> list[DictItem]:
        """根据字典类型ID查询所有字典项"""
        return await self.dict_item_dao.list_by_dict_type(dict_type_id)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """分页查询字典项列表"""
        items = await self.dict_item_dao.list_all(pagination)
        total = await self.dict_item_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """无限滚动查询字典项"""
        items: list[DictItem] = await self.dict_item_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def count_by_dict_type(self, dict_type_id: str) -> int:
        """统计指定字典类型的字典项数量"""
        return await self.dict_item_dao.count_by_dict_type(dict_type_id)