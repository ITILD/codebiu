from enum import Enum

from pydantic import BaseModel, Field


class VoiceEngine(str, Enum):
    """语音引擎方案: online(远程API或本地vllm发布, 协议细节放 extra.protocol) / local(本机onnx或qwen推理, 框架放 extra.engine)

    历史值 dashscope/sherpa/qwen 由 resolve_engine 归一化(旧请求兼容窗口)
    """

    ONLINE = "online"
    LOCAL = "local"


# 旧 engine 值 -> 新方案归一化映射(dashscope=在线, sherpa/qwen=本地)
_LEGACY_ENGINE_MAP: dict[str, VoiceEngine] = {
    "dashscope": VoiceEngine.ONLINE,
    "sherpa": VoiceEngine.LOCAL,
    "qwen": VoiceEngine.LOCAL,
}


def normalize_engine(raw: str | None) -> VoiceEngine | None:
    """归一化 engine 字符串为新方案枚举(旧值 dashscope/sherpa/qwen 兼容映射)

    :return: 对应 VoiceEngine; 空值返回 None(由模型配置自动选择); 无效值返回 None 交由上层回落
    """
    if not raw:
        return None
    raw = raw.strip().lower()
    if raw in _LEGACY_ENGINE_MAP:
        return _LEGACY_ENGINE_MAP[raw]
    try:
        return VoiceEngine(raw)
    except ValueError:
        return None


def resolve_engine(raw: str | None) -> VoiceEngine | None:
    """解析 engine 参数并归一化为新方案(online/local)

    - 空/None 返回 None, 由模型配置自动选择
    - 旧值兼容: dashscope->online, sherpa/qwen->local
    - 无效值回落 LOCAL(本地方案零外部依赖, 最稳)
    """
    engine = normalize_engine(raw)
    if engine is None and raw and raw.strip():
        return VoiceEngine.LOCAL
    return engine


class TTSRequest(BaseModel):
    """语音合成(TTS)请求模型"""

    text: str = Field(..., description="需要合成的文本内容")
    engine: str | None = Field(
        None, description="TTS 引擎方案: online/local(兼容旧值 dashscope/sherpa/qwen, 缺省按模型配置自动选择)"
    )
    speaker: int = Field(0, description="说话人 ID(多说话人模型使用)")
    speed: float = Field(1.0, description="语速倍率")
    sample_rate: int = Field(22050, description="目标采样率")


class ASRResponse(BaseModel):
    """语音识别(ASR)结果"""

    text: str = Field("", description="识别出的文本")
    engine: VoiceEngine = Field(VoiceEngine.LOCAL, description="使用的引擎方案(online/local)")
    elapsed: float = Field(0.0, description="耗时(秒)")


class ASRStreamMessage(BaseModel):
    """ASR 流式识别消息(WebSocket)"""

    text: str = Field("", description="当前识别文本")
    is_final: bool = Field(False, description="是否为最终结果")
    engine: VoiceEngine = Field(VoiceEngine.LOCAL, description="使用的引擎方案(online/local)")


class VADSegment(BaseModel):
    """VAD 检测出的单个语音段"""

    start: float = Field(0.0, description="语音段起始时间(秒)")
    duration: float = Field(0.0, description="语音段时长(秒)")


class VADResponse(BaseModel):
    """VAD 语音活动检测结果"""

    segments: list[VADSegment] = Field(default_factory=list, description="语音段列表")
    elapsed: float = Field(0.0, description="耗时(秒)")
