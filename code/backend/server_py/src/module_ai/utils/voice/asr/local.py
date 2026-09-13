"""本地(local) ASR 引擎: 按框架分派 sherpa(onnx CPU) / qwen(本地推理)"""
import logging

from module_ai.utils.voice.interface import ASREngine

logger = logging.getLogger(__name__)


class LocalASR(ASREngine):
    """本地方案 ASR 引擎: extra.engine 分派 SherpaASR(默认)/QwenASR, 方法全部透传"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 引擎配置(extra.engine=sherpa|qwen, 其余键透传给对应实现)
        """
        self._conf = conf or {}
        # extra(engine 等)已在 service._engine_conf 展平进 conf
        engine = str(self._conf.get("engine") or "sherpa").lower()
        if engine == "qwen":
            from module_ai.utils.voice.asr.qwen import QwenASR

            self._impl: ASREngine = QwenASR(self._conf)
        else:
            from module_ai.utils.voice.asr.sherpa import SherpaASR

            self._impl = SherpaASR(self._conf)

    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """离线识别完整音频"""
        return self._impl.recognize(audio_bytes, sample_rate)

    def create_stream(self):
        """创建流式识别会话"""
        return self._impl.create_stream()

    def stream_accept(self, stream, samples, sample_rate: int = 16000) -> str:
        """向流式会话送入一帧 PCM 样本"""
        return self._impl.stream_accept(stream, samples, sample_rate)

    def stream_result(self, stream, is_final: bool = False) -> str:
        """获取流式会话的当前文本"""
        return self._impl.stream_result(stream, is_final)

    def stream_destroy(self, stream) -> None:
        """销毁流式会话"""
        self._impl.stream_destroy(stream)
