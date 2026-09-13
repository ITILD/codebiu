"""ASR 语音识别子包: online(远程API或本地vllm发布) / local(sherpa onnx 或 qwen 本地推理)

协议/框架细节按 extra 分派:
- online + extra.protocol=dashscope: 百炼 qwen3-asr-flash(整段) / paraformer-realtime·gummy(实时 WS 流式)
- online + extra.protocol=openai: OpenAI 兼容 /v1/audio/transcriptions
- local + extra.engine=sherpa|qwen: 本机 onnx / 本地大模型推理
"""
from .dashscope import DashscopeASR
from .local import LocalASR
from .online import OnlineASR
from .qwen import QwenASR
from .sherpa import SherpaASR

__all__ = ["SherpaASR", "QwenASR", "DashscopeASR", "OnlineASR", "LocalASR"]
