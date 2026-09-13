"""本地(local) TTS 引擎: 按框架分派 sherpa(onnx CPU) / qwen(本地推理)"""
import logging
from typing import Iterator, Tuple

from module_ai.utils.voice.interface import TTSEngine

logger = logging.getLogger(__name__)


class LocalTTS(TTSEngine):
    """本地方案 TTS 引擎: extra.engine 分派 SherpaTTS(默认)/QwenTTS, 方法全部透传"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 引擎配置(extra.engine=sherpa|qwen, 其余键透传给对应实现)
        """
        self._conf = conf or {}
        # extra(engine 等)已在 service._engine_conf 展平进 conf
        engine = str(self._conf.get("engine") or "sherpa").lower()
        if engine == "qwen":
            from module_ai.utils.voice.tts.qwen import QwenTTS

            self._impl: TTSEngine = QwenTTS(self._conf)
        else:
            from module_ai.utils.voice.tts.sherpa import SherpaTTS

            self._impl = SherpaTTS(self._conf)

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        """合成完整音频"""
        return self._impl.synthesize(text, speaker, speed, sample_rate)

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[Tuple[bytes, int, bool]]:
        """流式合成(透传实现类的切片/真流式逻辑)"""
        yield from self._impl.synthesize_stream(text, speaker, speed, sample_rate)
