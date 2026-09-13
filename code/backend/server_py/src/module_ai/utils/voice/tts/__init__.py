"""TTS 语音合成子包: online(远程API或本地vllm发布) / local(sherpa onnx 或 qwen 本地推理)

协议/框架细节按 extra 分派:
- online + extra.protocol=dashscope: 百炼 CosyVoice 流式 WebSocket / 非流式 HTTP
- online + extra.protocol=openai: OpenAI 兼容 /v1/audio/speech
- local + extra.engine=sherpa|qwen: 本机 onnx / 本地大模型推理
"""
from .dashscope import DashscopeTTS
from .local import LocalTTS
from .online import OnlineTTS
from .qwen import QwenTTS
from .sherpa import SherpaTTS

__all__ = ["SherpaTTS", "QwenTTS", "DashscopeTTS", "OnlineTTS", "LocalTTS"]
