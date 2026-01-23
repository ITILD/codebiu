from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_main.do.dict_type import DictType, DictTypeCreate, DictTypeUpdate
from module_main.dao.dict_type import DictTypeDao


class DictTypeService:
    """字典类型服务"""

    def __init__(self, dict_type_dao: DictTypeDao):
        self.dict_type_dao = dict_type_dao or DictTypeDao()

    async def add(self, dict_type: DictTypeCreate) -> str:
        """新增字典类型"""
        return await self.dict_type_dao.add(dict_type)

    async def delete(self, id: str) -> None:
        """删除字典类型"""
        await self.dict_type_dao.delete(id)

    async def update(self, dict_type_id: str, dict_type: DictTypeUpdate) -> None:
        """更新字典类型"""
        await self.dict_type_dao.update(dict_type_id, dict_type)

    async def get(self, id: str) -> DictType | None:
        """获取单个字典类型"""
        return await self.dict_type_dao.get(id)

    async def get_by_code(self, type_code: str) -> DictType | None:
        """根据编码获取字典类型"""
        return await self.dict_type_dao.get_by_code(type_code)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """分页查询字典类型列表"""
        items = await self.dict_type_dao.list_all(pagination)
        total = await self.dict_type_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """无限滚动查询字典类型"""
        items: list[DictType] = await self.dict_type_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)