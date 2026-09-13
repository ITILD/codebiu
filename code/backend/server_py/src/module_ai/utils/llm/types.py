from enum import Enum


class ModelServerType(str, Enum):
    """
    模型服务类型枚举 openai vllm ollama sherpa qwen paddle online local
    - chat/embeddings/rerank 类: openai/dashscope/vllm/ollama/aws
    - asr/tts 类: online(远程API或本地vllm发布, 协议细节放 extra.protocol) / local(本机onnx或qwen推理, 框架放 extra.engine)
    - ocr 类: dashscope(阿里云在线) / paddle(本地 PP-OCR onnx)
    - vad/denoise 类: local(本机 sherpa-onnx)
    - dashscope/sherpa/qwen 为语音历史方案值: ORM 存量行仍按值读取, 禁止删除
    """

    OPENAI = "openai"
    DASHSCOPE = "dashscope"
    VLLM = "vllm"
    OLLAMA = "ollama"
    AWS = "aws"
    SHERPA = "sherpa"
    QWEN = "qwen"
    PADDLE = "paddle"
    ONLINE = "online"
    LOCAL = "local"


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
    - asr/tts: online(远程API或本地vllm发布, 优先 qwen3 系列) / local(本机 onnx 或 qwen 推理)
    - ocr: dashscope(阿里云在线) + paddle(本地 PP-OCR onnx)
    - vad/denoise: 本地 sherpa-onnx 实时/轻量推理, 仅 local 方案
    :param model_type: 模型类型
    :return: 服务方案列表
    """
    value = model_type.value if isinstance(model_type, ModelType) else str(model_type)
    if value in ("asr", "tts"):
        return [ModelServerType.ONLINE, ModelServerType.LOCAL]
    if value == "ocr":
        return [ModelServerType.DASHSCOPE, ModelServerType.PADDLE]
    if value in ("vad", "denoise"):
        return [ModelServerType.LOCAL]
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
