"""TTS 语音合成子包: sherpa(CPU 轻量) 与 qwen(GPU 大模型) 双方案"""
from .qwen import QwenTTS
from .sherpa import SherpaTTS

__all__ = ["SherpaTTS", "QwenTTS"]
