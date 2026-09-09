"""语音控制器辅助工具"""
from module_ai.do.voice import VoiceEngine


def resolve_engine(raw: str | None) -> VoiceEngine | None:
    """解析 engine 参数(空/None 时返回 None 由模型配置自动选择)"""
    if not raw:
        return None
    try:
        return VoiceEngine(raw)
    except ValueError:
        return VoiceEngine.SHERPA
