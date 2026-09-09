"""sherpa-onnx 降噪引擎实现(GTCRN, CPU 实时语音降噪)

引擎配置来源优先级:
    1. model_config 表(model_type=denoise, server_type=sherpa)的 model/extra 字段
    2. config.yaml 的 voice.sherpa 静态配置(默认回落)
"""
import logging
from pathlib import Path

import numpy as np

from module_ai.config.voice import DIR_VOICE_MODEL, SHERPA_DENOISE_MODEL
from module_ai.utils.voice.interface import DenoiseEngine

logger = logging.getLogger(__name__)


class SherpaDenoise(DenoiseEngine):
    """基于 GTCRN 的语音降噪引擎(OfflineSpeechDenoiser)"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: gtcrn onnx 文件名(相对 voice 模型根目录)或绝对路径
        """
        self._conf = conf or {}
        self._denoiser = None

    @property
    def _model_path(self) -> Path:
        name = self._conf.get("model")
        if name:
            p = Path(str(name))
            return p if p.is_absolute() else DIR_VOICE_MODEL / p
        return SHERPA_DENOISE_MODEL

    def _ensure(self):
        if self._denoiser is not None:
            return self._denoiser
        try:
            import sherpa_onnx
        except ImportError as e:
            raise RuntimeError(
                "未安装 sherpa-onnx，无法使用 sherpa 降噪。请执行 `pip install sherpa-onnx`"
            ) from e
        model_path = self._model_path
        if not model_path.exists():
            raise RuntimeError(f"GTCRN 降噪模型不存在: {model_path}，请下载模型放置到该目录")

        cfg = sherpa_onnx.OfflineSpeechDenoiserConfig()
        cfg.model.gtcrn.model = str(model_path)
        self._denoiser = sherpa_onnx.OfflineSpeechDenoiser(cfg)
        logger.info("sherpa 降噪(GTCRN) 加载完成: %s", model_path.name)
        return self._denoiser

    def enhance(self, samples: np.ndarray, sample_rate: int) -> tuple[np.ndarray, int]:
        denoiser = self._ensure()
        denoised = denoiser.run(np.asarray(samples, dtype=np.float32), sample_rate)
        return np.asarray(denoised.samples, dtype=np.float32), denoised.sample_rate
