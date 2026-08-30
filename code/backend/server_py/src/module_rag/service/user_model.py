from module_rag.do.user_model import UserModel, UserModelUpdate
from module_rag.dao.user_model import UserModelDao
from langchain_core.language_models import BaseChatModel
from module_ai.service.llm_base import LLMBaseService
from module_ai.utils.llm.do.llm_type import ModelType
import logging

logger = logging.getLogger(__name__)


class UserModelService:
    """用户-模型绑定服务"""

    def __init__(
        self,
        user_model_dao: UserModelDao | None = None,
        llm_base_service: LLMBaseService | None = None,
    ):
        self.user_model_dao = user_model_dao or UserModelDao()
        self.llm_base_service = llm_base_service or LLMBaseService()

    async def get_by_user(self, user_id: str) -> UserModel | None:
        """
        获取用户的模型绑定
        :param user_id: 用户ID
        :return: 用户-模型绑定对象
        """
        return await self.user_model_dao.get_by_user(user_id)

    async def upsert(self, user_id: str, user_model: UserModelUpdate) -> UserModel:
        """
        新增或更新用户的模型绑定(存在则更新，不存在则创建)
        :param user_id: 用户ID
        :param user_model: 更新数据
        :return: 绑定记录
        """
        existing = await self.user_model_dao.get_by_user(user_id)
        if existing:
            await self.user_model_dao.update_by_user(user_id, user_model)
            return await self.user_model_dao.get_by_user(user_id)
        # 不存在则创建
        create_data = user_model.model_dump(exclude_unset=True)
        new_record = UserModel(user_id=user_id, **create_data)
        await self.user_model_dao.add(new_record)
        # 重新查询以确保返回数据库生成的字段(id/created_at/updated_at)
        return await self.user_model_dao.get_by_user(user_id)

    async def get_llm_by_user_id(
        self, user_id: str, streaming: bool = True, model_type: ModelType = ModelType.CHAT
    ) -> BaseChatModel | None:
        """根据用户ID获取用户绑定的对话模型"""
        try:
            binding = await self.get_by_user(user_id)
            llm = None
            match model_type:
                case ModelType.CHAT:
                    llm = await self.llm_base_service.get_llm(
                        binding.chat_model_id, streaming=streaming
                    )
                case ModelType.EMBEDDINGS:
                    llm = await self.llm_base_service.get_llm(binding.embedding_model_id, False)
                case ModelType.RERANK:
                    llm = await self.llm_base_service.get_llm(binding.rerank_model_id, False)
            return llm
        except Exception as e:
            logger.error(f"获取用户绑定对话模型失败: {e}")
            return None
