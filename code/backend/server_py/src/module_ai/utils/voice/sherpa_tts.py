"""sherpa-onnx TTS 引擎实现(offline VITS)"""
import logging
from typing import Iterator, Tuple

from module_ai.config.voice import (
    SHERPA_TTS_DICT_DIR,
    SHERPA_TTS_LEXICON,
    SHERPA_TTS_MAX_NUM_SENTENCES,
    SHERPA_TTS_MODEL,
    SHERPA_TTS_TOKENS,
)
from module_ai.utils.voice.audio_utils import to_pcm16
from module_ai.utils.voice.interface import TTSEngine
logger = logging.getLogger(__name__)


class SherpaTTS(TTSEngine):
    def __init__(self):
        self._tts = None

    def _ensure(self):
        if self._tts is not None:
            return self._tts

        try:
            # https://github.com/k2-fsa/sherpa-onnx/issues/2791 解决 OfflineTts 未初始化问题
            from sherpa_onnx import OfflineTts, OfflineTtsConfig, OfflineTtsModelConfig, OfflineTtsVitsModelConfig
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx，无法使用 sherpa TTS。请执行 `pip install sherpa-onnx`"
            ) from e
        if not SHERPA_TTS_MODEL.exists():
            raise RuntimeError(
                f"sherpa TTS 模型不存在: {SHERPA_TTS_MODEL}，请下载模型放置到该目录"
            )
        vits = OfflineTtsVitsModelConfig(
            model=str(SHERPA_TTS_MODEL),
            tokens=str(SHERPA_TTS_TOKENS),
            lexicon=str(SHERPA_TTS_LEXICON) if SHERPA_TTS_LEXICON.exists() else "",
            dict_dir=str(SHERPA_TTS_DICT_DIR) if SHERPA_TTS_DICT_DIR.exists() else "",
        )
        model_cfg = OfflineTtsModelConfig(vits=vits)
        cfg = OfflineTtsConfig(
            model=model_cfg,
            max_num_sentences=SHERPA_TTS_MAX_NUM_SENTENCES,
        )
        self._tts = OfflineTts(cfg)
        logger.info("sherpa TTS OfflineTts 加载完成")
        return self._tts

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        tts = self._ensure()
        audio = tts.generate(text, sid=speaker, speed=speed)
        samples = __import__("numpy").asarray(audio.samples, dtype="float32")
        return to_pcm16(samples), int(audio.sample_rate)

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[Tuple[bytes, int, bool]]:
        # sherpa offline TTS 一次性生成，按句切片流式返回
        pcm, sr = self.synthesize(text, speaker, speed, sample_rate)
        chunk_bytes = int(sr * 0.2) * 2  # 200ms
        total = len(pcm)
        offset = 0
        while offset < total:
            chunk = pcm[offset : offset + chunk_bytes]
            offset += chunk_bytes
            yield chunk, sr, offset >= total
        if total == 0:
            yield b"", sr, True
