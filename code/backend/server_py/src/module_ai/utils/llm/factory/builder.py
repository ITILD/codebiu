"""模型实例工厂: 按模型配置(model_config 表记录)构建 LangChain 可调用实例

支持方案(ModelServerType):
    - openai / dashscope: OpenAI 兼容协议(chat 走 ChatQwenWithReasoning 以保留思考内容)
    - ollama: 本地 Ollama 协议
    - aws: Bedrock Converse
    - vllm: 暂未实现(抛 ValueError)
"""
import logging

from langchain_aws import BedrockEmbeddings, ChatBedrockConverse
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from module_ai.do.model_config import ModelConfig
from module_ai.utils.llm.chat.think import ChatQwenWithReasoning
from module_ai.utils.llm.types import ModelType, ModelServerType

logger = logging.getLogger(__name__)


def build_chat_model(config: ModelConfig, streaming: bool = True) -> BaseChatModel:
    """按配置构建对话(chat)模型实例

    :param config: 模型配置
    :param streaming: 是否启用流式输出
    :raises ValueError: 服务方案暂未实现
    """
    if config.server_type in (ModelServerType.OPENAI, ModelServerType.DASHSCOPE):
        return ChatQwenWithReasoning(
            model=config.model,
            api_key=config.api_key,
            base_url=config.url,
            streaming=streaming,
            temperature=config.temperature,
            extra_body={"enable_thinking": not config.no_think},
        )
    if config.server_type == ModelServerType.OLLAMA:
        return ChatOllama(
            model=config.model,
            base_url=config.url,
            streaming=streaming,
            temperature=config.temperature,
        )
    if config.server_type == ModelServerType.AWS:
        aws_access_key_id = (config.extra or {}).get("aws_access_key_id")
        region_name = (config.extra or {}).get("region_name")
        return ChatBedrockConverse(
            provider="anthropic",
            model=config.model,
            aws_access_key_id=SecretStr(aws_access_key_id),
            aws_secret_access_key=SecretStr(config.api_key),
            region_name=region_name,
            max_tokens=config.out_tokens,
        )
    raise ValueError(f"服务方案 {config.server_type} 的对话模型暂未实现")


def build_embeddings(config: ModelConfig) -> Embeddings:
    """按配置构建向量化(embeddings)模型实例

    :raises ValueError: 服务方案暂未实现
    """
    if config.server_type in (ModelServerType.OPENAI, ModelServerType.DASHSCOPE):
        # jina-embeddings 不支持 dimensions 参数
        dimensions = config.out_tokens
        if "jina-embeddings" in config.model:
            dimensions = None
        return OpenAIEmbeddings(
            model=config.model,
            api_key=config.api_key,
            base_url=config.url,
            dimensions=dimensions,
            # qwen 系模型向量化长度检查关闭
            check_embedding_ctx_length=False,
        )
    if config.server_type == ModelServerType.OLLAMA:
        return OllamaEmbeddings(
            model=config.model,
            base_url=config.url,
            dimensions=config.out_tokens,
        )
    if config.server_type == ModelServerType.AWS:
        aws_access_key_id = (config.extra or {}).get("aws_access_key_id")
        region_name = (config.extra or {}).get("region_name")
        return BedrockEmbeddings(
            model_id=config.model,
            aws_access_key_id=SecretStr(aws_access_key_id),
            aws_secret_access_key=SecretStr(config.api_key),
            region_name=region_name,
        )
    raise ValueError(f"服务方案 {config.server_type} 的向量化模型暂未实现")


def build_model(
    config: ModelConfig, streaming: bool = True
) -> BaseChatModel | Embeddings:
    """按 model_type 分派构建模型实例(chat/embeddings, 其余类型抛 ValueError)"""
    if config.model_type == ModelType.CHAT:
        return build_chat_model(config, streaming)
    if config.model_type == ModelType.EMBEDDINGS:
        return build_embeddings(config)
    raise ValueError(f"暂不支持的模型类型: {config.model_type}")
