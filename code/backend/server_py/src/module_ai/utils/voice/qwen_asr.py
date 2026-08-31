"""Qwen3-ASR-1.7B 引擎实现

通过 transformers 加载本地 Qwen3-ASR 模型，将音频识别为文本。
依赖 torch + transformers(已在 pyproject 中)。

引擎配置来源优先级:
    1. model_config 表(model_type=asr, server_type=qwen)的 model/extra 字段
    2. config.yaml 的 voice.qwen 静态配置(默认回落)
"""
import logging
from pathlib import Path
from typing import Any

from module_ai.config.voice import DIR_VOICE_MODEL, QWEN_ASR_MODEL_DIR, QWEN_DEVICE, VOICE_ASR_SAMPLE_RATE
from module_ai.utils.voice.audio_utils import load_audio, resample_linear
from module_ai.utils.voice.interface import ASREngine

logger = logging.getLogger(__name__)


class QwenASR(ASREngine):
    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: ASR 模型目录名(相对 voice 模型根目录)或绝对路径
            - device: 推理设备(cpu/cuda)
        """
        self._conf = conf or {}
        self._model = None
        self._processor = None

    @property
    def _model_dir(self) -> Path:
        name = self._conf.get("model")
        if name:
            p = Path(str(name))
            return p if p.is_absolute() else DIR_VOICE_MODEL / p
        return QWEN_ASR_MODEL_DIR

    @property
    def _device(self) -> str:
        return str(self._conf.get("device", QWEN_DEVICE))

    def _ensure(self):
        if self._model is not None:
            return self._model, self._processor
        model_dir = self._model_dir
        if not model_dir.exists():
            raise RuntimeError(
                f"Qwen3-ASR 模型不存在: {model_dir}，请下载模型放置到该目录"
            )
        try:
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
        except ImportError as e:
            raise RuntimeError(
                "未安装 torch/transformers，无法使用 Qwen3-ASR。请执行 `pip install torch transformers`"
            ) from e

        try:
            self._processor = AutoProcessor.from_pretrained(
                str(model_dir), trust_remote_code=True
            )
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                str(model_dir),
                torch_dtype=getattr(torch, "float32"),
                low_cpu_mem_usage=True,
                trust_remote_code=True,
            ).to(self._device).eval()
        except Exception:
            # 兜底：部分 Qwen ASR 模型以 AutoModel 方式加载
            from transformers import AutoModel

            self._model = AutoModel.from_pretrained(
                str(model_dir),
                trust_remote_code=True,
            ).to(self._device).eval()
        logger.info("Qwen3-ASR 模型加载完成: %s", model_dir.name)
        return self._model, self._processor

    def recognize(self, audio_bytes: bytes, sample_rate: int = VOICE_ASR_SAMPLE_RATE) -> str:
        model, processor = self._ensure()
        samples, sr = load_audio(audio_bytes)
        if sr != sample_rate:
            samples = resample_linear(samples, sr, sample_rate)

        try:
            import torch

            inputs = processor(
                samples, sampling_rate=sample_rate, return_tensors="pt"
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            with torch.no_grad():
                generated_ids = model.generate(**inputs, max_new_tokens=512)
            text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return str(text).strip()
        except Exception as e:
            logger.error(f"Qwen3-ASR 识别失败: {e}")
            raise RuntimeError(f"Qwen3-ASR 识别失败: {e}") from e

    # Qwen3-ASR 为离线模型，流式场景下复用离线识别(在 WS 中按最终结果输出)
    def create_stream(self):
        return {"buffer": bytearray()}

    def stream_accept(self, stream, samples, sample_rate: int = VOICE_ASR_SAMPLE_RATE) -> str:
        from module_ai.utils.voice.audio_utils import to_pcm16
        import numpy as np

        if isinstance(samples, (bytes, bytearray)):
            stream["buffer"].extend(samples)
        else:
            stream["buffer"].extend(to_pcm16(np.asarray(samples, dtype=np.float32)))
        return ""

    def stream_result(self, stream, is_final: bool = False) -> str:
        if not is_final:
            return ""
        if not stream["buffer"]:
            return ""
        pcm = bytes(stream["buffer"])
        return self.recognize(pcm, sample_rate=VOICE_ASR_SAMPLE_RATE)

    def stream_destroy(self, stream) -> None:
        stream["buffer"].clear()
