from enum import Enum


class ModelServerType(str, Enum):
    """
    模型服务类型枚举 openai vllm ollama
    """

    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    VLLM = "vllm"
    OLLAMA = "ollama"
    AWS = "aws"


class ModelType(str, Enum):
    """
    模型类型枚举 chat embeddings rerank
    """

    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    RERANK = "rerank"


# 角色
class Role(str, Enum):
    """
    消息角色枚举 system user assistant
    """

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# langchain消息类型
class LCRole(str, Enum):
    """
    langchain消息类型枚举 system human ai
    """

    SYSTEM = "system"
    USHUMAN = "human"
    AI = "ai"
