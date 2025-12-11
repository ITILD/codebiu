from langchain_core.runnables import RunnableSequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from module_ai.do.model_config import ModelConfig, ModelConfigCreateRequest
from module_ai.service.model_config import ModelConfigService
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_aws import BedrockEmbeddings, ChatBedrock
from module_ai.do.llm_base import (
    Message,
    ChatRequest,
    EmbeddingRequest,
    CacheClearRequest,
)
from pydantic import SecretStr
from module_ai.utils.llm.do.model_type import ModelType, ModelServerType
import logging

logger = logging.getLogger(__name__)


class LLMBaseService:
    """
    LLM基础服务类，提供统一的大语言模型调用接口
    集成模型配置管理、AI工厂创建和基础调用方法
    使用单例模式确保全局唯一实例
    """

    _instance = None
    _initialized = False

    def __new__(cls, model_config_service: ModelConfigService | None = None):
        """
        单例模式实现
        """
        if cls._instance is None:
            cls._instance = super(LLMBaseService, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_config_service: ModelConfigService | None = None):
        """
        初始化LLM基础服务

        Args:
            model_config_service: 模型配置服务实例，如果不提供则创建默认实例
        """
        # 确保初始化只执行一次
        if not self.__class__._initialized:
            self.model_config_service = model_config_service or ModelConfigService()
            self._model_cache: dict[str, RunnableSequence] = {}
            self.__class__._initialized = True

    async def check_config(self, model_config_create_request: ModelConfigCreateRequest):
        llm_chain = self._llm_by_config(model_config_create_request)
        result = await llm_chain.ainvoke("1+1=? only return result number")
        # 判断包含2
        return "2" in result.content

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
        # 由于ChatRequest的验证器已自动处理消息转换，messages现在一定是Message列表
        messages = [msg.to_langchain_message() for msg in request.messages]
        try:
            # 调用模型
            if request.streaming:
                return llm_chain.astream(messages)
            return llm_chain.ainvoke(messages)
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
            # if config.model_type == ModelType.CHAT:
            #     return ChatBedrock(
            #     provider="anthropic",
            #     model_id=config.model,
            #     aws_access_key_id=SecretStr(config.aws_access_key_id),
            #     aws_secret_access_key=SecretStr(config.aws_secret_access_key),
            #     region=config.region_name,
            #     streaming=streaming,
            # )
            # elif config.model_type == ModelType.EMBEDDINGS:
            # result_embeddings = BedrockEmbeddings(
            #     model_id="amazon.titan-embed-text-v2:0",
            #     aws_access_key_id=SecretStr(""),
            #     aws_secret_access_key=SecretStr(""),
            #     region_name="ap-northeast-1",
            # )
            pass


# 全局服务实例(通过单例模式确保全局唯一)
llm_base_service = LLMBaseService()
