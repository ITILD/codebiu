"""sherpa-onnx TTS 引擎实现(offline VITS)

引擎配置来源优先级:
    1. model_config 表(model_type=tts, server_type=sherpa)的 model/extra 字段
    2. config.yaml 的 voice.sherpa 静态配置(默认回落)
"""
import logging
from pathlib import Path
from typing import Iterator, Tuple

from module_ai.config.voice import (
    DIR_VOICE_MODEL,
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
    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: TTS 模型目录名(相对 voice 模型根目录)或 onnx 文件路径
            - tts_model/tts_tokens/tts_lexicon/tts_dict_dir: 各文件路径覆盖
            - max_num_sentences: 单次合成最长句数
        """
        self._conf = conf or {}
        self._tts = None

    # ---- 配置解析(动态优先, 静态回落) ----
    def _conf_path(self, key: str, fallback: Path, base: Path) -> Path:
        name = self._conf.get(key)
        if name:
            p = Path(str(name))
            return p if p.is_absolute() else base / p
        return fallback

    @property
    def _model(self) -> Path:
        # model 字段可以是目录名(拼默认文件名)或 onnx 文件路径
        name = self._conf.get("model")
        if name:
            p = Path(str(name))
            if p.suffix == ".onnx":
                return p if p.is_absolute() else DIR_VOICE_MODEL / p
            base = DIR_VOICE_MODEL / p
            model = self._conf_path("tts_model", SHERPA_TTS_MODEL, base)
            return model
        return self._conf_path("tts_model", SHERPA_TTS_MODEL, DIR_VOICE_MODEL)

    @property
    def _tokens(self) -> Path:
        return self._conf_path("tts_tokens", SHERPA_TTS_TOKENS, self._model.parent)

    @property
    def _lexicon(self) -> Path:
        return self._conf_path("tts_lexicon", SHERPA_TTS_LEXICON, self._model.parent)

    @property
    def _dict_dir(self) -> Path:
        return self._conf_path("tts_dict_dir", SHERPA_TTS_DICT_DIR, self._model.parent)

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
        model_path = self._model
        if not model_path.exists():
            raise RuntimeError(
                f"sherpa TTS 模型不存在: {model_path}，请下载模型放置到该目录"
            )
        vits = OfflineTtsVitsModelConfig(
            model=str(model_path),
            tokens=str(self._tokens),
            lexicon=str(self._lexicon) if self._lexicon.exists() else "",
            dict_dir=str(self._dict_dir) if self._dict_dir.exists() else "",
        )
        model_cfg = OfflineTtsModelConfig(vits=vits)
        cfg = OfflineTtsConfig(
            model=model_cfg,
            max_num_sentences=int(self._conf.get("max_num_sentences", SHERPA_TTS_MAX_NUM_SENTENCES)),
        )
        self._tts = OfflineTts(cfg)
        logger.info("sherpa TTS OfflineTts 加载完成: %s", model_path.name)
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
