"""LLM 服务: chat/embeddings 模型的统一调用入口

职责:
    - 按模型配置加载 LangChain 模型实例(构建统一走 utils.llm.factory 工厂, 本服务不重复实现)
    - chat 对话(流式/非流式) 与 embeddings 调用
    - 模型配置连通性/格式化能力校验
    - 模型实例缓存管理(按 model_id+streaming 缓存, 配置变更由调用方 clear_cache)
"""
import logging

from langchain.agents import create_agent
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import RunnableSequence

from module_ai.do.llm import (
    ChatRequest,
    ModelChatCheckFormat,
    ModelConfigCheckResponse,
)
from module_ai.do.model_config import ModelConfig, ModelConfigCreateRequest
from module_ai.service.model_config import ModelConfigService
from module_ai.utils.llm.factory.builder import build_model
from module_ai.utils.llm.prompts.base import LLMPrompt
from module_ai.utils.llm.types import ModelType

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM 服务类，提供统一的大语言模型调用接口
    集成模型配置管理、模型工厂构建和基础调用方法
    使用单例模式确保全局唯一实例
    """

    def __init__(
        self,
        model_config_service: ModelConfigService | None = None,
        llm_prompt: LLMPrompt | None = None,
    ):
        """
        初始化LLM服务

        Args:
            model_config_service: 模型配置服务实例，如果不提供则创建默认实例
        """
        self.model_config_service = model_config_service or ModelConfigService()
        self.llm_prompt = llm_prompt or LLMPrompt()
        self._model_cache: dict[str, BaseChatModel | Embeddings] = {}

    async def check_config(
        self, model_config_create_request: ModelConfigCreateRequest
    ) -> ModelConfigCheckResponse:
        """校验模型配置连通性与输出格式(创建/修改模型配置时使用)

        :param model_config_create_request: 待校验的模型配置
        :return: 校验结果(是否有效/是否支持格式化)
        """
        # 模型构建失败(方案未实现/参数缺失)视为校验失败, 不向上抛
        try:
            llm_chain = build_model(model_config_create_request)
        except Exception as e:
            logger.warning(f"模型构建失败: {e}")
            return ModelConfigCheckResponse()
        model_config_check_response = ModelConfigCheckResponse()
        if model_config_create_request.model_type == ModelType.CHAT:
            # 校验简单问答 判断包含2
            try:
                result_chat = await llm_chain.ainvoke("1+1=? only return result number")
                model_config_check_response.is_valid = "2" in result_chat.content
            except Exception as e:
                logger.warning(f"校验模型连通性失败: {e}")
                model_config_check_response.is_valid = False
                return model_config_check_response
            # 校验format格式
            try:
                messages = await self.llm_prompt.get_prompt_format_check()
                agent = create_agent(
                    model=llm_chain,
                    response_format=ModelChatCheckFormat,
                )
                result_format = await agent.ainvoke({"messages": messages})
                model_chat_check_format: ModelChatCheckFormat = (
                    ModelChatCheckFormat.model_validate(
                        result_format["structured_response"]
                    )
                )
                model_config_check_response.is_format = (
                    model_chat_check_format.age is int(100)
                )
            except Exception as e:
                logger.warning(f"校验format格式失败: {e}")
        elif model_config_create_request.model_type == ModelType.EMBEDDINGS:
            try:
                aembed_result = await llm_chain.aembed_query("你好啊")
                model_config_check_response.is_valid = len(aembed_result) > 0
            except Exception as e:
                logger.warning(f"校验向量化模型失败: {e}")
                model_config_check_response.is_valid = False
        else:
            logger.error(f"不支持的模型类型: {model_config_create_request.model_type}")
        return model_config_check_response

    async def check_config_by_model_id(self, model_id: str) -> bool:
        """
        校验模型配置是否有效

        Args:
            model_id: 模型配置ID或模型标识名称
        Returns:
            bool: 模型配置是否有效
        """
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            return False
        result = await self.check_config(config)
        return result.is_valid

    async def get_llm(
        self, model_id: str, streaming: bool = True
    ) -> BaseChatModel | Embeddings | None:
        """
        按模型配置获取模型实例(带缓存)

        Args:
            model_id: 模型配置ID或模型标识名称
            streaming: 是否启用流式响应

        Returns:
            模型实例，配置不存在时返回 None
        """
        # 检查缓存
        cache_key = f"{model_id}_{streaming}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        # 获取模型配置
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            return None

        # 经模型工厂构建实例并缓存
        llm_chain = build_model(config, streaming)
        self._model_cache[cache_key] = llm_chain
        return llm_chain

    async def chat_completion(self, request: ChatRequest):
        """聊天完成接口"""
        # 获取LLM处理链
        llm_chain: BaseChatModel = await self.get_llm(request.model_id, streaming=request.streaming)
        # request.messages 是langchain类型
        try:
            # 调用模型
            if request.streaming:
                return llm_chain.astream(request.messages)
            result = await llm_chain.ainvoke(request.messages)
            return result.content
        except Exception as e:
            logger.error(f"模型调用失败: {e}")
            raise

    def clear_cache(self, model_id: str | None = None):
        """
        清除模型缓存

        Args:
            model_id: 模型配置ID或模型标识名称，如果为None则清除所有缓存
        """
        if model_id:
            # 清除指定模型的缓存
            keys_to_remove = []
            for key in self._model_cache.keys():
                if key.startswith(model_id):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._model_cache[key]
        else:
            # 清除所有缓存
            self._model_cache.clear()
