"""模型实例工厂: 按模型配置(model_config 表记录)构建 LangChain 可调用实例

支持方案(ModelServerType):
    - openai / dashscope: OpenAI 兼容协议(chat 走 ChatQwenWithReasoning 以保留思考内容)
    - ollama: 本地 Ollama 协议
    - aws: Bedrock Converse
    - vllm: rerank 类型专用(jina 兼容 /v1/rerank 协议)
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
from module_ai.utils.llm.rerank.interface import Rerank
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
            timeout=config.timeout,  # 请求超时(秒), 不传时底层默认过长易挂起
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
        extra = config.extra or {}
        aws_access_key_id = extra.get("aws_access_key_id")
        region_name = extra.get("region_name")
        return ChatBedrockConverse(
            provider="anthropic",
            model=config.model,
            # 凭证缺失时传 None 交由 boto 凭证链解析, 避免 SecretStr(None) TypeError
            aws_access_key_id=SecretStr(aws_access_key_id) if aws_access_key_id else None,
            aws_secret_access_key=SecretStr(config.api_key) if config.api_key else None,
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
            timeout=config.timeout,  # 请求超时(秒)
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
) -> BaseChatModel | Embeddings | Rerank:
    """按 model_type 分派构建模型实例(chat/embeddings/rerank, 其余类型抛 ValueError)"""
    if config.model_type == ModelType.CHAT:
        return build_chat_model(config, streaming)
    if config.model_type == ModelType.EMBEDDINGS:
        return build_embeddings(config)
    if config.model_type == ModelType.RERANK:
        return build_rerank_model(config)
    raise ValueError(f"暂不支持的模型类型: {config.model_type}")


def build_rerank_model(config: ModelConfig) -> Rerank:
    """按配置构建重排序引擎实例(分数范围从 extra.score_min/score_max 读取)

    分数量纲约定:
        - 默认 0~1(Qwen/gte 系、经 sigmoid 的 bge 系)
        - jina-reranker-v3 等输出 -0.5~0.5 的模型: extra 配置 {"score_min": -0.5, "score_max": 0.5}
        - 归一化在 Rerank 基类统一完成, 上游 score_threshold 一律按 0~1 语义
    """
    extra = config.extra or {}

    def _range() -> tuple[float, float]:
        """读取并校验分数范围, 非法时回退 0~1"""
        try:
            score_min = float(extra["score_min"])
            score_max = float(extra["score_max"])
        except (KeyError, TypeError, ValueError):
            return 0.0, 1.0
        if score_max <= score_min:
            logger.warning(
                "rerank 分数范围非法(score_max<=score_min): %s/%s, 回退 0~1",
                score_min, score_max,
            )
            return 0.0, 1.0
        return score_min, score_max

    score_min, score_max = _range()

    if config.server_type == ModelServerType.DASHSCOPE:
        from module_ai.utils.llm.rerank.impl.dashscope import DashscopeRerank

        return DashscopeRerank(
            api_key=config.api_key,
            model=config.model,
            base_url=config.url
            or "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
            score_min=score_min,
            score_max=score_max,
        )
    if config.server_type == ModelServerType.OLLAMA:
        from module_ai.utils.llm.rerank.impl.ollama import OllamaRerank

        return OllamaRerank(
            model=config.model,
            base_url=config.url or "http://localhost:11434/api/rerank",
            score_min=score_min,
            score_max=score_max,
        )
    if config.server_type == ModelServerType.VLLM:
        from module_ai.utils.llm.rerank.impl.vllm import VllmRerank

        return VllmRerank(
            model=config.model,
            base_url=config.url or "http://localhost:10002/v1/rerank",
            score_threshold=extra.get("score_threshold"),
            api_key=config.api_key,
            score_min=score_min,
            score_max=score_max,
        )
    raise ValueError(f"服务方案 {config.server_type} 暂不支持重排序")
