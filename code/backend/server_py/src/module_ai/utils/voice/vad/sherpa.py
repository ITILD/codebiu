"""sherpa-onnx VAD 引擎实现(silero-vad, CPU 实时语音活动检测)

引擎配置来源优先级:
    1. model_config 表(model_type=vad, server_type=sherpa)的 model/extra 字段
    2. config.yaml 的 voice.sherpa 静态配置(默认回落)
"""
import logging
from pathlib import Path

import numpy as np

from module_ai.config.voice import DIR_VOICE_MODEL, SHERPA_VAD_MODEL, VOICE_VAD_SAMPLE_RATE
from module_ai.utils.voice.interface import VADEngine

logger = logging.getLogger(__name__)


class SherpaVAD(VADEngine):
    """基于 silero-vad 的实时语音活动检测引擎

    流式使用方式:
        vad.accept_waveform(frame)          # 持续送入 PCM 帧
        vad.is_speech_detected()            # 判断是否有语音
        segment = vad.pop_speech_segment()  # 取出完整语音段
    """

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: silero-vad onnx 文件名(相对 voice 模型根目录)或绝对路径
            - threshold: 语音判定阈值(0~1)
            - min_silence_duration: 触发切分的最小静音时长(秒)
            - min_speech_duration: 丢弃的最短语音时长(秒)
            - buffer_size_in_seconds: 内部缓冲区大小(秒)
        """
        self._conf = conf or {}
        self._vad = None

    @property
    def _model_path(self) -> Path:
        name = self._conf.get("model")
        if name:
            p = Path(str(name))
            return p if p.is_absolute() else DIR_VOICE_MODEL / p
        return SHERPA_VAD_MODEL

    def _ensure(self):
        if self._vad is not None:
            return self._vad
        try:
            import sherpa_onnx
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx，无法使用 sherpa VAD。请执行 `pip install sherpa-onnx`"
            ) from e
        model_path = self._model_path
        if not model_path.exists():
            raise RuntimeError(f"silero VAD 模型不存在: {model_path}，请下载模型放置到该目录")

        cfg = sherpa_onnx.VadModelConfig()
        cfg.silero_vad.model = str(model_path)
        cfg.silero_vad.threshold = float(self._conf.get("threshold", 0.5))
        cfg.silero_vad.min_silence_duration = float(self._conf.get("min_silence_duration", 0.25))
        cfg.silero_vad.min_speech_duration = float(self._conf.get("min_speech_duration", 0.5))
        cfg.sample_rate = VOICE_VAD_SAMPLE_RATE
        buffer_seconds = float(self._conf.get("buffer_size_in_seconds", 100))

        self._vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=buffer_seconds)
        logger.info("sherpa VAD 加载完成: %s", model_path.name)
        return self._vad

    def accept_waveform(self, samples: np.ndarray) -> None:
        self._ensure().accept_waveform(np.asarray(samples, dtype=np.float32))

    def is_speech_detected(self) -> bool:
        return self._ensure().is_speech_detected()

    def pop_speech_segment(self) -> tuple[np.ndarray, int] | None:
        vad = self._ensure()
        if vad.empty():
            return None
        segment = vad.front  # SpeechSegment(samples, start_index)
        vad.pop()
        return np.asarray(segment.samples, dtype=np.float32), segment.start

    def reset(self) -> None:
        if self._vad is not None:
            self._vad.reset()

    def flush(self) -> None:
        if self._vad is not None:
            self._vad.flush()
