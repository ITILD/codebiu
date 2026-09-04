# self
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_life.do.baby_name import (
    BabyName,
    BabyNameCreate,
    BabyNameUpdate,
    BabyNameBatchDelete,
)
from module_life.utils.baby_name.do.baby_name import (
    NameInfoBase,
    NameInfoFull,
    NameInfoResultList,
    NameInfoResult,
    NameInfoPreference,
    NameInfoResultExplanation,
    NameInfoResultBase,
    NameInfoEX,
    NameInfoPredictFull,
)
from module_life.dao.baby_name import BabyNameDao
from module_ai.service.llm_base import LLMBaseService
# lib
# from config.db import async_transaction
from src.module_life.utils.baby_name.baby_name import baby_name_generator

class BabyNameService:
    """宝宝名字服务"""

    def __init__(self, baby_name_dao: BabyNameDao, llm_base_service: LLMBaseService):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.baby_name_dao = baby_name_dao or BabyNameDao()
        self.llm_base_service = llm_base_service or LLMBaseService()

    async def predict_name_info_preference_by_ai(
        self, name_info_base: NameInfoBase
    ) -> NameInfoPreference:
        """
        根据宝宝天生信息推测宝宝名字的偏好信息
        :param name_info_base: 宝宝天生信息
        :return: 推测的偏好信息
        """
        # 这里可以添加智能推测偏好信息的逻辑
        return NameInfoPreference()

    async def predict_name_by_ai(
        self, name_info_base: NameInfoBase
    ) -> NameInfoResultList:
        """
        根据宝宝全部基础信息推测宝宝名字
        :param name_info_base: 姓名信息基础数据
        :return: 推测结果列表
        """
        # 这里可以添加智能推测名字的逻辑
        # 目前先返回空列表，后续可以集成AI推测名字的功能
        return NameInfoResultList(results=[])
    
    async def predict_baby_info_base_by_ai(
        self, name_info_predict_full: NameInfoPredictFull,model_id:str
    ) -> NameInfoResultList:
        """
        根据宝宝全部基础信息推测宝宝名字
        :param name_info_predict_full: 姓名信息基础数据
        :return: 推测结果列表
        """
        model = await self.llm_base_service.get_llm(model_id)
        # 这里可以添加智能推测名字的逻辑
        # 目前先返回空列表，后续可以集成AI推测名字的功能
        return baby_name_generator.generate_stream(name_info_predict_full, model)

    async def predict_name_explanation_by_ai(
        self, name_info_result_base: NameInfoResultBase
    ) -> NameInfoResultExplanation:
        """
        根据姓名信息推测宝宝名字的偏好信息和寓意
        :param name_info_result_base: 姓名基础信息
        :return: 推测的解释
        """
        # 这里可以添加智能推测解释的逻辑
        return NameInfoResultExplanation()

    async def add(self, baby_name: BabyNameCreate) -> str:
        """
        添加新的宝宝名字
        :param baby_name: 宝宝名字创建数据
        :return: 创建的名字ID
        """
        return await self.baby_name_dao.add(baby_name)

    async def delete(self, id: str):
        """
        删除宝宝名字
        :param id: 名字ID
        """
        await self.baby_name_dao.delete(id)

    async def batch_delete(self, batch_delete: BabyNameBatchDelete) -> int:
        """
        批量删除宝宝名字
        :param batch_delete: 批量删除请求
        :return: 删除的记录数
        """
        return await self.baby_name_dao.batch_delete(batch_delete)

    async def update(self, name_id: str, baby_name: BabyNameUpdate):
        """
        更新宝宝名字信息
        :param name_id: 名字ID
        :param baby_name: 更新数据
        """
        await self.baby_name_dao.update(name_id, baby_name)

    async def get(self, id: str) -> BabyName | None:
        """
        获取单个宝宝名字
        :param id: 名字ID
        :return: 宝宝名字信息或None
        """
        return await self.baby_name_dao.get(id)

    async def list_paged(self, pagination: PaginationParams):
        """
        获取宝宝名字列表
        :param pagination: 分页参数
        :return: 分页响应数据
        """
        items = await self.baby_name_dao.list_paged(pagination)
        total = await self.baby_name_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams):
        """
        滚动加载宝宝名字列表
        :param params: 滚动参数
        :return: 滚动响应数据
        """
        items: list[BabyName] = await self.baby_name_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)

    async def search_names(
        self, keyword: str, gender: str | None = None, style: str | None = None
    ) -> list[BabyName]:
        """
        搜索宝宝名字
        :param keyword: 搜索关键词
        :param gender: 性别过滤
        :param style: 风格过滤
        :return: 搜索结果列表
        """
        # 这里可以添加搜索逻辑
        # 目前先返回空列表，后续可以集成搜索功能
        return []

    async def get_popular_names(self, limit: int = 20) -> list[BabyName]:
        """
        获取热门宝宝名字
        :param limit: 返回数量
        :return: 热门名字列表
        """
        # 这里可以添加获取热门名字的逻辑
        # 目前先返回空列表，后续可以根据流行度排序
        return []


if __name__ == "__main__":
    import asyncio

    async def main():
        service = BabyNameService()

        print(await service.get_popular_names())

    asyncio.run(main())
