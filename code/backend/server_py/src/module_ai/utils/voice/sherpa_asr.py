"""sherpa-onnx ASR 引擎实现

- 离线识别：OfflineRecognizer(用于音频上传识别)
- 在线流式识别：OnlineRecognizer(用于麦克风实时流式识别)
"""
import logging
from typing import Any

import numpy as np

from module_ai.config.voice import (
    SHERPA_ASR_MODEL_DIR,
    SHERPA_ASR_TOKENS,
    VOICE_ASR_SAMPLE_RATE,
)
from module_ai.utils.voice.audio_utils import load_audio, resample_linear
from module_ai.utils.voice.interface import ASREngine

logger = logging.getLogger(__name__)


class SherpaASR(ASREngine):
    def __init__(self):
        self._offline = None
        self._online_cfg = None

    # ---- 离线识别 ----
    def _ensure_offline(self):
        if self._offline is not None:
            return self._offline
        try:
            from sherpa_onnx import OfflineRecognizer
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx，无法使用 sherpa ASR。请执行 `pip install sherpa-onnx`"
            ) from e
        if not SHERPA_ASR_MODEL_DIR.exists():
            raise RuntimeError(
                f"sherpa ASR 模型不存在: {SHERPA_ASR_MODEL_DIR}，请下载模型放置到该目录"
            )
        self._offline = OfflineRecognizer.from_pretrained(
            model_type="zipformer",
            model_dir=str(SHERPA_ASR_MODEL_DIR),
            tokens=str(SHERPA_ASR_TOKENS),
            num_threads=1,
            decoding_method="greedy_search",
        )
        logger.info("sherpa ASR OfflineRecognizer 加载完成")
        return self._offline

    def recognize(self, audio_bytes: bytes, sample_rate: int = VOICE_ASR_SAMPLE_RATE) -> str:
        recognizer = self._ensure_offline()
        samples, sr = load_audio(audio_bytes)
        if sr != sample_rate:
            samples = resample_linear(samples, sr, sample_rate)
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, samples.tolist() if isinstance(samples, np.ndarray) else samples)
        recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        return text

    # ---- 在线流式识别 ----
    def _ensure_online(self):
        if self._online_cfg is not None:
            return self._online_cfg
        try:
            from sherpa_onnx import (
                OnlineRecognizer,
                OnlineTransducerModelConfig,
                OnlineParaformerModelConfig,
                OnlineZipformer2ModelConfig,
                FeatureConfig,
            )
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx，无法使用 sherpa 流式 ASR。请执行 `pip install sherpa-onnx`"
            ) from e
        if not SHERPA_ASR_MODEL_DIR.exists():
            raise RuntimeError(
                f"sherpa ASR 模型不存在: {SHERPA_ASR_MODEL_DIR}，请下载模型放置到该目录"
            )
        # 流式 zipformer 双语模型
        zipformer = OnlineZipformer2ModelConfig(str(SHERPA_ASR_MODEL_DIR))
        model_cfg = OnlineParaformerModelConfig()  # 占位
        transducer_cfg = OnlineTransducerModelConfig(
            encoder=str(SHERPA_ASR_MODEL_DIR / "encoder-epoch-99-avg-1.onnx"),
            decoder=str(SHERPA_ASR_MODEL_DIR / "decoder-epoch-99-avg-1.onnx"),
            joiner=str(SHERPA_ASR_MODEL_DIR / "joiner-epoch-99-avg-1.onnx"),
        )
        feat_cfg = FeatureConfig(sample_rate=VOICE_ASR_SAMPLE_RATE, feature_dim=80)
        try:
            recognizer = OnlineRecognizer(
                transducer=transducer_cfg,
                zipformer2=zipformer,
                tokens=str(SHERPA_ASR_TOKENS),
                feat=feat_cfg,
                num_threads=1,
                decoding_method="greedy_search",
            )
        except Exception:
            # 不同模型目录结构差异，回退到 from_pretrained(部分版本不支持)
            recognizer = OnlineRecognizer.from_pretrained(
                model_type="zipformer2",
                model_dir=str(SHERPA_ASR_MODEL_DIR),
                tokens=str(SHERPA_ASR_TOKENS),
            )
        self._online_cfg = {"recognizer": recognizer, "feat": feat_cfg}
        logger.info("sherpa ASR OnlineRecognizer 加载完成")
        return self._online_cfg

    def create_stream(self):
        cfg = self._ensure_online()
        return cfg["recognizer"].create_stream()

    def stream_accept(self, stream, samples, sample_rate: int = VOICE_ASR_SAMPLE_RATE) -> str:
        cfg = self._ensure_online()
        recognizer = cfg["recognizer"]
        if isinstance(samples, (bytes, bytearray)):
            from module_ai.utils.voice.audio_utils import pcm16_to_float32

            samples = pcm16_to_float32(bytes(samples))
        stream.accept_waveform(sample_rate, np.asarray(samples, dtype=np.float32))
        recognizer.decode_stream(stream)
        return stream.result.text.strip()

    def stream_result(self, stream, is_final: bool = False) -> str:
        cfg = self._ensure_online()
        if is_final:
            cfg["recognizer"].decode_stream(stream)
        text = stream.result.text.strip()
        if is_final:
            cfg["recognizer"].reset(stream)
        return text

    def stream_destroy(self, stream) -> None:
        try:
            cfg = self._ensure_online()
            cfg["recognizer"].reset(stream)
        except Exception:
            pass
