"""语音控制器包(按模型类别拆分: ASR/TTS/VAD/降噪)

接口(路由前缀 /voice):
    - asr.py      POST /asr         语音识别(音频上传)
                  WS   /asr/stream  语音识别(麦克风实时流式)
    - tts.py      POST /tts/file    语音合成(返回完整音频文件 wav)
                  POST /tts/stream  语音合成(流式返回 PCM)
    - vad.py      POST /vad         语音活动检测(切分语音段)
    - denoise.py  POST /denoise     语音降噪(返回降噪后 wav)

engine 参数可选：缺省时按模型配置(model_config 表 model_type=asr/tts/vad/denoise)
自动选择方案；也可显式指定 sherpa / qwen 覆盖(vad/denoise 仅 sherpa)。
"""
# 导入各模型类别控制器, 触发路由注册(module_app.include_router)
from module_ai.controller.voice import asr, denoise, tts, vad  # noqa: F401
