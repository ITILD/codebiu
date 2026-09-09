"""voice 语音工具包: 按子任务划分的 asr/tts/vad/denoise 引擎包

子包职责(每种任务均以 interface.py 抽象接口为统一契约):
    - asr:     语音识别 - SherpaASR(CPU 轻量流式) / QwenASR(GPU 大模型)
    - tts:     语音合成 - SherpaTTS(CPU 轻量 VITS) / QwenTTS(GPU 大模型)
    - vad:     语音活动检测 - SherpaVAD(silero-vad, CPU 实时)
    - denoise: 语音降噪 - SherpaDenoise(GTCRN, CPU 实时)
    - audio:   音频加载/重采样/PCM 转换公共工具
设备方案: sherpa 系列跑 CPU(onnxruntime), qwen 系列跑 GPU(torch, QWEN_DEVICE 可配)。
"""
from module_ai.utils.voice.asr import QwenASR, SherpaASR
from module_ai.utils.voice.denoise import SherpaDenoise
from module_ai.utils.voice.interface import ASREngine, DenoiseEngine, TTSEngine, VADEngine
from module_ai.utils.voice.tts import QwenTTS, SherpaTTS
from module_ai.utils.voice.vad import SherpaVAD

__all__ = [
    "ASREngine", "TTSEngine", "VADEngine", "DenoiseEngine",
    "SherpaASR", "QwenASR", "SherpaTTS", "QwenTTS", "SherpaVAD", "SherpaDenoise",
]
