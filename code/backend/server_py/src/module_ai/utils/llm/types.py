from enum import Enum


class ModelServerType(str, Enum):
    """
    模型服务类型枚举 openai vllm ollama sherpa qwen
    - chat/embeddings/rerank 类: openai/dashscope/vllm/ollama/aws
    - asr/tts/ocr 类: sherpa/qwen(本地推理方案, 模型路径等放 extra)
    """

    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    VLLM = "vllm"
    OLLAMA = "ollama"
    AWS = "aws"
    SHERPA = "sherpa"
    QWEN = "qwen"


class ModelType(str, Enum):
    """
    模型类型枚举 chat embeddings rerank ocr asr tts vad denoise
    """

    CHAT = "chat"
    EMBEDDINGS = "embeddings"
    RERANK = "rerank"
    OCR = "ocr"
    ASR = "asr"
    TTS = "tts"
    VAD = "vad"
    DENOISE = "denoise"


def server_types_for(model_type: "ModelType | str") -> list[ModelServerType]:
    """
    按模型类型返回可用的服务方案(前端下拉/后端校验共用)
    - asr/tts: sherpa(轻量 CPU) 与 qwen(大模型 GPU) 双方案
    - vad/denoise/ocr: 本地 sherpa-onnx 实时/轻量推理, 仅 sherpa 方案
    :param model_type: 模型类型
    :return: 服务方案列表
    """
    value = model_type.value if isinstance(model_type, ModelType) else str(model_type)
    if value in ("asr", "tts"):
        return [ModelServerType.SHERPA, ModelServerType.QWEN]
    if value in ("vad", "denoise", "ocr"):
        return [ModelServerType.SHERPA]
    return [
        ModelServerType.OPENAI,
        ModelServerType.DASHSCOPE,
        ModelServerType.VLLM,
        ModelServerType.OLLAMA,
        ModelServerType.AWS,
    ]


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
