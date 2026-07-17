from module_ai.service.voice import VoiceService

# 全局单例(引擎内部模型懒加载)
voice_service = VoiceService()


def get_voice_service() -> VoiceService:
    """获取语音服务单例"""
    return voice_service
