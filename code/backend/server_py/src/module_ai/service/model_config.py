# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_ai.do.model_config import ModelConfig, ModelConfigCreate, ModelConfigUpdate
from module_ai.dao.model_config import ModelConfigDao


class ModelConfigService:
    """模型配置服务层"""

    def __init__(self, model_config_dao: ModelConfigDao =None):
        self.model_config_dao = model_config_dao or ModelConfigDao()

    async def add(self, model_config: ModelConfigCreate) -> str:
        """
        添加新的模型配置
        :param model_config: 模型配置数据
        :return: 创建的模型配置ID
        """
        # TODO 检查模型标识是否已存在 
        existing_config = False
        if existing_config:
            raise ValueError(f"模型标识 '{model_config.model}' 已存在")
        return await self.model_config_dao.add(model_config)

    async def delete(self, id: str):
        """
        删除模型配置
        :param id: 模型配置ID
        """
        await self.model_config_dao.delete(id)

    async def update(self, model_config_id: str, model_config: ModelConfigUpdate):
        """
        更新模型配置
        :param model_config_id: 模型配置ID
        :param model_config: 更新的模型配置数据
        """
        await self.model_config_dao.update(model_config_id, model_config)

    async def get(self, id: str) -> ModelConfig | None:
        """
        获取单个模型配置
        :param id: 模型配置ID
        :return: 模型配置对象
        """
        return await self.model_config_dao.get(id)


    async def list(self, pagination: PaginationParams) -> PaginationResponse:
        """
        分页获取模型配置列表
        :param pagination: 分页参数
        :return: 分页响应数据
        """
        items = await self.model_config_dao.list(pagination)
        total = await self.model_config_dao.count()
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(self, params: InfiniteScrollParams) -> InfiniteScrollResponse:
        """
        滚动加载模型配置列表
        :param params: 滚动参数
        :return: 滚动响应数据
        """
        items = await self.model_config_dao.get_scroll(params)
        return InfiniteScrollResponse.create(items, params.limit)
    

if __name__ == "__main__":
    import asyncio
    from common.config.index import conf
    model_config_service = ModelConfigService()
    async def main():
        model_conf = conf.ai.aliyun.chat_mini
        # 添加一份
        model_obj = ModelConfigCreate(**model_conf.to_dict())
        await model_config_service.add(model_obj)
        pass
    asyncio.run(main())