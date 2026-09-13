"""语音控制器辅助工具"""
from module_ai.do.voice import VoiceEngine, normalize_engine


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
