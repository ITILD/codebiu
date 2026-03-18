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
class RoleType(str, Enum):
    """
    消息角色枚举 system user assistant
    """

    SYSTEM = "system"
    USER = "user"  # "human"
    ASSISTANT = "assistant"  # 对应"ai"


# langchain消息类型
class LCRoleType(str, Enum):
    """
    langchain消息类型枚举 system human ai
    """

    SYSTEM = "system"
    USHUMAN = "human"
    AI = "ai"


class StreamStatus(str, Enum):
    """
    流式响应状态枚举 start stream end
    """

    START = "start"
    STREAM = "stream"
    END = "end"
    ERROR = "error"
