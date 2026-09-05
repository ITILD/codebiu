from common.utils.db.schema.pagination import (
    InfiniteScrollParams, 
    InfiniteScrollResponse, 
    PaginationParams, 
    PaginationResponse
)
from module_nlp.do.synonym import (
    SynonymGroup, 
    SynonymGroupCreate, 
    SynonymGroupUpdate, 
    SynonymGroupBatchDelete,
    Synonym,
    SynonymCreate,
    SynonymBatchCreate,
    SynonymBatchDelete
)
from module_nlp.dao.synonym import SynonymGroupDao, SynonymDao


class SynonymGroupService:
    """同义词组服务"""

    def __init__(self, synonym_group_dao: SynonymGroupDao):
        self.synonym_group_dao = synonym_group_dao or SynonymGroupDao()

    async def add(self, synonym_group: SynonymGroupCreate) -> str:
        """新增同义词组"""
        return await self.synonym_group_dao.add(synonym_group)

    async def delete(self, id: str) -> None:
        """删除同义词组"""
        await self.synonym_group_dao.delete(id)

    async def delete_by_id_and_pid(self, id: str, pid: str) -> None:
        """
        通过ID和项目ID删除同义词组及组内所有同义词
        :param id: 要删除的同义词组ID
        :param pid: 项目ID
        """
        await self.synonym_group_dao.delete_by_id_and_pid(id, pid)

    async def batch_delete(self, batch_delete: SynonymGroupBatchDelete) -> int:
        """批量删除同义词组及组内所有同义词"""
        return await self.synonym_group_dao.batch_delete(batch_delete)

    async def batch_delete_by_ids_and_pid(
        self, batch_delete: SynonymGroupBatchDelete, pid: str
    ) -> int:
        """
        通过ID列表和项目ID批量删除同义词组及组内所有同义词
        :param batch_delete: 批量删除同义词组请求模型
        :param pid: 项目ID
        :return: 实际删除的记录数
        """
        return await self.synonym_group_dao.batch_delete_by_ids_and_pid(batch_delete, pid)

    async def update(self, synonym_group_id: str, synonym_group: SynonymGroupUpdate) -> str:
        """更新同义词组"""
        return await self.synonym_group_dao.update(synonym_group_id, synonym_group)

    async def get(self, id: str) -> SynonymGroup | None:
        """获取单个同义词组"""
        return await self.synonym_group_dao.get(id)

    async def get_by_id_and_pid(self, id: str, pid: str) -> SynonymGroup | None:
        """
        通过ID和项目ID获取单个同义词组
        :param id: 同义词组ID
        :param pid: 项目ID
        :return: 同义词组详情
        """
        return await self.synonym_group_dao.get_by_id_and_pid(id, pid)

    async def list_all(self, pagination: PaginationParams) -> PaginationResponse:
        """分页查询同义词组列表"""
        items = await self.synonym_group_dao.list_all(pagination)
        total = await self.synonym_group_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def list_all_by_pid(
        self, pagination: PaginationParams, pid: str
    ) -> PaginationResponse:
        """
        分页查询指定项目的同义词组列表
        :param pagination: 分页参数
        :param pid: 项目ID
        :return: 分页响应结果
        """
        items = await self.synonym_group_dao.list_all_by_pid(pagination, pid)
        total = await self.synonym_group_dao.count_by_pid(pid)
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """无限滚动查询同义词组"""
        items = await self.synonym_group_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def get_scroll_by_pid(
        self, params: InfiniteScrollParams, pid: str
    ) -> InfiniteScrollResponse:
        """
        无限滚动查询指定项目的同义词组
        :param params: 无限滚动参数
        :param pid: 项目ID
        :return: 无限滚动响应结果
        """
        items = await self.synonym_group_dao.get_scroll_by_pid(params, pid)
        return InfiniteScrollResponse.create(items, params.limit)


class SynonymService:
    """同义词服务"""

    def __init__(self, synonym_dao: SynonymDao):
        self.synonym_dao = synonym_dao or SynonymDao()

    async def add(self, synonym: SynonymCreate) -> str:
        """新增单个同义词"""
        return await self.synonym_dao.add(synonym)

    async def batch_add(self, batch_create: SynonymBatchCreate) -> list[str]:
        """批量新增同义词"""
        return await self.synonym_dao.batch_add(batch_create)

    async def delete(self, id: str) -> None:
        """删除同义词"""
        await self.synonym_dao.delete(id)

    async def delete_by_id_and_pid(self, id: str, pid: str) -> None:
        """
        通过ID和项目ID删除同义词
        :param id: 要删除的同义词ID
        :param pid: 项目ID
        """
        await self.synonym_dao.delete_by_id_and_pid(id, pid)

    async def batch_delete(self, batch_delete: SynonymBatchDelete) -> int:
        """批量删除同义词"""
        return await self.synonym_dao.batch_delete(batch_delete)

    async def batch_delete_by_ids_and_pid(
        self, batch_delete: SynonymBatchDelete, pid: str
    ) -> int:
        """
        根据ID列表和项目ID批量删除同义词
        :param batch_delete: 批量删除同义词请求模型
        :param pid: 项目ID
        :return: 实际删除的记录数
        """
        return await self.synonym_dao.batch_delete_by_ids_and_pid(batch_delete, pid)

    async def get(self, id: str) -> Synonym | None:
        """获取单个同义词"""
        return await self.synonym_dao.get(id)

    async def list_by_group(
        self, 
        group_id: str, 
        pagination: PaginationParams
    ) -> list[Synonym]:
        """根据同义词组ID查询同义词列表"""
        return await self.synonym_dao.list_by_group(group_id, pagination)

    async def search_by_word(
        self, 
        word: str, 
        pid: str,
        language: str | None = None
    ) -> list[Synonym]:
        """
        根据词语搜索同义词组的所有同义词
        :param word: 要搜索的词语
        :param pid: 项目ID
        :param language: 语言代码(可选)
        :return: 该词语所在同义词组的所有同义词列表
        """
        return await self.synonym_dao.search_by_word(word, pid, language)

    async def batch_search_by_words(
        self, 
        words: list[str], 
        pid: str,
        language: str | None = None
    ) -> list[Synonym]:
        """
        批量根据词语搜索同义词组的所有同义词
        :param words: 要搜索的词语列表
        :param pid: 项目ID
        :param language: 语言代码(可选)
        :return: 所有词语所在同义词组的所有同义词列表
        """
        return await self.synonym_dao.batch_search_by_words(words, pid, language)

    async def get_synonyms_by_group(
        self, 
        group_id: str
    ) -> list[str]:
        """获取同义词组的所有同义词(仅返回词语列表)"""
        return await self.synonym_dao.get_synonyms_by_group(group_id)

    async def count(self) -> int:
        """统计同义词总数"""
        return await self.synonym_dao.count()