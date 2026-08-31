from enum import Enum

from pydantic import BaseModel, Field


class VoiceEngine(str, Enum):
    """语音引擎类型：sherpa(默认) / qwen"""

    SHERPA = "sherpa"
    QWEN = "qwen"


class TTSRequest(BaseModel):
    """语音合成(TTS)请求模型"""

    text: str = Field(..., description="需要合成的文本内容")
    engine: VoiceEngine | None = Field(
        None, description="TTS 引擎: sherpa/qwen(缺省按模型配置自动选择)"
    )
    speaker: int = Field(0, description="说话人 ID(多说话人模型使用)")
    speed: float = Field(1.0, description="语速倍率")
    sample_rate: int = Field(22050, description="目标采样率")


class ASRResponse(BaseModel):
    """语音识别(ASR)结果"""

    text: str = Field("", description="识别出的文本")
    engine: VoiceEngine = Field(VoiceEngine.SHERPA, description="使用的引擎")
    elapsed: float = Field(0.0, description="耗时(秒)")


class ASRStreamMessage(BaseModel):
    """ASR 流式识别消息(WebSocket)"""

    text: str = Field("", description="当前识别文本")
    is_final: bool = Field(False, description="是否为最终结果")
    engine: VoiceEngine = Field(VoiceEngine.SHERPA, description="使用的引擎")
