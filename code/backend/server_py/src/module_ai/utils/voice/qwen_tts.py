"""Qwen3-TTS-1.7B 引擎实现

通过 transformers 加载本地 Qwen3-TTS 模型，将文本合成为语音。
模型需下载到 temp_source/model/voice/Qwen3-TTS-1.7B 目录。

注：Qwen3-TTS 具体推理接口随模型卡片而定，此处采用通用的
AutoModel + generate 调用，并对结果做兼容处理。如模型卡片要求
特定调用方式，可在此处按需调整。
"""
import logging
from typing import Iterator, Tuple

from module_ai.config.voice import QWEN_DEVICE, QWEN_TTS_MODEL_DIR
from module_ai.utils.voice.audio_utils import to_pcm16
from module_ai.utils.voice.interface import TTSEngine

logger = logging.getLogger(__name__)

DEFAULT_TTS_SAMPLE_RATE = 22050


class QwenTTS(TTSEngine):
    def __init__(self):
        self._model = None
        self._processor = None

    def _ensure(self):
        if self._model is not None:
            return self._model, self._processor
        if not QWEN_TTS_MODEL_DIR.exists():
            raise RuntimeError(
                f"Qwen3-TTS 模型不存在: {QWEN_TTS_MODEL_DIR}，请下载模型放置到该目录"
            )
        try:
            import torch
            from transformers import AutoModel, AutoProcessor
        except ImportError as e:
            raise RuntimeError(
                "未安装 torch/transformers，无法使用 Qwen3-TTS。请执行 `pip install torch transformers`"
            ) from e

        self._processor = AutoProcessor.from_pretrained(
            str(QWEN_TTS_MODEL_DIR), trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            str(QWEN_TTS_MODEL_DIR),
            torch_dtype=getattr(torch, "float32"),
            trust_remote_code=True,
        ).to(QWEN_DEVICE).eval()
        logger.info("Qwen3-TTS 模型加载完成")
        return self._model, self._processor

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        model, processor = self._ensure()
        try:
            import torch
            import numpy as np

            inputs = processor(text=text, return_tensors="pt")
            inputs = {k: v.to(QWEN_DEVICE) for k, v in inputs.items()}
            with torch.no_grad():
                output = model.generate(**inputs, **{
                    "speaker_id": speaker,
                    "speed": speed,
                })

            # 兼容多种返回结构
            audio = None
            sr = sample_rate
            if isinstance(output, dict):
                audio = output.get("audio") or output.get("waveform")
                sr = output.get("sampling_rate") or output.get("sample_rate") or sr
            elif hasattr(output, "audio"):
                audio = output.audio
                sr = getattr(output, "sampling_rate", sr)
            elif isinstance(output, (list, tuple)):
                audio = output[0]
            else:
                audio = output

            if hasattr(processor, "batch_decode") and audio is not None and not isinstance(
                audio, (np.ndarray, list, torch.Tensor)
            ):
                audio = processor.batch_decode(audio)[0]

            if audio is None:
                raise RuntimeError("Qwen3-TTS 未返回音频数据，请检查模型卡片调用方式")

            samples = np.asarray(audio, dtype="float32").reshape(-1)
            # 归一化
            m = float(np.max(np.abs(samples)) or 1.0)
            if m > 1.0:
                samples = samples / m
            return to_pcm16(samples), int(sr or sample_rate)
        except Exception as e:
            logger.error(f"Qwen3-TTS 合成失败: {e}")
            raise RuntimeError(f"Qwen3-TTS 合成失败: {e}") from e

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[Tuple[bytes, int, bool]]:
        pcm, sr = self.synthesize(text, speaker, speed, sample_rate)
        chunk_bytes = int(sr * 0.2) * 2
        total = len(pcm)
        offset = 0
        while offset < total:
            chunk = pcm[offset : offset + chunk_bytes]
            offset += chunk_bytes
            yield chunk, sr, offset >= total
        if total == 0:
            yield b"", sr, True
