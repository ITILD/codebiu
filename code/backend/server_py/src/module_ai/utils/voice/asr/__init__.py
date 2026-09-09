"""ASR 语音识别子包: sherpa(CPU 轻量) 与 qwen(GPU 大模型) 双方案"""
from .qwen import QwenASR
from .sherpa import SherpaASR

__all__ = ["SherpaASR", "QwenASR"]
