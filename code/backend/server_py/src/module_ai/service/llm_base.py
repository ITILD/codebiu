from langchain_core.runnables import RunnableSequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from module_ai.do.model_config import ModelConfig, ModelConfigCreateRequest
from module_ai.service.model_config import ModelConfigService
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langchain.agents import create_agent
from module_ai.do.llm_base import (
    Message,
    ChatRequest,
    EmbeddingRequest,
    CacheClearRequest,
    ModelChatCheckFormat,
    ModelConfigCheckResponse,
)
from pydantic import SecretStr
from module_ai.utils.llm.do.model_type import ModelType, ModelServerType
from module_ai.dao.llm_base_prompt import LLMBasePrompt
import logging

logger = logging.getLogger(__name__)


class LLMBaseService:
    """
    LLM基础服务类，提供统一的大语言模型调用接口
    集成模型配置管理、AI工厂创建和基础调用方法
    使用单例模式确保全局唯一实例
    """
    def __init__(
        self,
        model_config_service: ModelConfigService | None = None,
        llm_base_prompt: LLMBasePrompt | None = None,
    ):
        """
        初始化LLM基础服务

        Args:
            model_config_service: 模型配置服务实例，如果不提供则创建默认实例
        """
        self.model_config_service = model_config_service or ModelConfigService()
        self.llm_base_prompt = llm_base_prompt or LLMBasePrompt()
        self._model_cache: dict[str, RunnableSequence] = {}

    async def check_config(
        self, model_config_create_request: ModelConfigCreateRequest
    ) -> ModelConfigCheckResponse:
        llm_chain = self._llm_by_config(model_config_create_request)
        # ModelConfigCheckResponse
        model_config_check_response = ModelConfigCheckResponse()
        if model_config_create_request.model_type == ModelType.CHAT:
            # 校验简单问答 判断包含2
            result_chat = await llm_chain.ainvoke("1+1=? only return result number")
            model_config_check_response.is_valid = "2" in result_chat.content
            # 校验format格式
            try:
                messages = await self.llm_base_prompt.get_prompt_format_check()
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
                pass
        elif model_config_create_request.model_type == ModelType.EMBEDDINGS:
            aembed_result = await llm_chain.aembed_query("1")
            model_config_check_response.is_valid = len(aembed_result) > 0
        # TODO rerank
        # elif model_config_create_request.model_type == ModelType.RERANK:
        #     result = await llm_chain.arank_documents(
        #         query="1", documents=["1", "2", "3"]
        #     )
        #     # 判断包含2
        #     return len(result) > 0
        else:
            logger.error(f"不支持的模型类型: {model_config_create_request.model_type}")
        return model_config_check_response

    async def check_config_by_model_id(self, model_id: str):
        """
        校验模型配置是否有效

        Args:
            model_id: 模型配置ID或模型标识名称
        """
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            return False
        return await self.check_config(config)

    async def get_llm(self, model_id: str, streaming: bool = True):
        """
        获取LLM处理链的基础llm对象

        Args:
            model_id: 模型配置ID或模型标识名称
            streaming: 是否启用流式响应

        Returns:
            LLM处理链，如果获取失败返回None
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

        # 转换为LLM配置
        llm_chain = self._llm_by_config(config)

        return llm_chain

    async def chat_completion(self, request: ChatRequest):
        """聊天完成接口"""
        # 获取LLM处理链
        llm_chain = await self.get_llm(request.model_id, streaming=request.streaming)
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

    def _llm_by_config(self, config: ModelConfig, streaming: bool = True):
        """将数据库模型配置转换为LLM配置对象"""
        # Ollama模型检测   ChatOpenAI, OpenAIEmbeddings
        if config.server_type == ModelServerType.OPENAI:
            if config.model_type == ModelType.CHAT:
                return ChatOpenAI(
                    model=config.model,
                    api_key=config.api_key,
                    base_url=config.url,
                    streaming=streaming,
                    temperature=config.temperature,
                )
            elif config.model_type == ModelType.EMBEDDINGS:
                return OpenAIEmbeddings(
                    model=config.model,
                    api_key=config.api_key,
                    base_url=config.url,
                    dimensions=config.out_tokens,
                )
        elif config.server_type == ModelServerType.OLLAMA:
            pass
        elif config.server_type == ModelServerType.VLLM:
            pass
        elif config.server_type == ModelServerType.AWS:
            aws_access_key_id = config.extra.get("aws_access_key_id")
            region_name = config.extra.get("region_name")
            if config.model_type == ModelType.CHAT:
                return ChatBedrockConverse(
                    provider="anthropic",
                    model_id=config.model,
                    aws_access_key_id=SecretStr(aws_access_key_id),
                    aws_secret_access_key=SecretStr(config.api_key),
                    region_name=region_name,
                    max_tokens=config.out_tokens,
                )
            elif config.model_type == ModelType.EMBEDDINGS:
                return BedrockEmbeddings(
                    model_id=config.model,
                    aws_access_key_id=SecretStr(aws_access_key_id),
                    aws_secret_access_key=SecretStr(config.api_key),
                    region_name=region_name,
                )
