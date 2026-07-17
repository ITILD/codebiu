"""音频处理工具：加载、重采样、格式转换"""
import io
import logging
import wave
from typing import Tuple

import numpy as np

logger = logging.getLogger(__name__)


def load_audio(audio_bytes: bytes) -> Tuple[np.ndarray, int]:
    """加载音频字节，返回 (float32 单声道样本, 采样率)

    优先使用 soundfile 解码各种格式(WAV/MP3/FLAC/OGG ...)，
    soundfile 不可用时回退到标准库 wave 仅支持 WAV。
    """
    # 1. soundfile
    try:
        import soundfile as sf

        samples, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=False)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        return samples, int(sr)
    except Exception as e:
        logger.debug(f"soundfile 解码失败，回退 wave: {e}")

    # 2. wave (仅 WAV)
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
        dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sample_width]
        arr = np.frombuffer(raw, dtype=dtype).astype(np.float32)
        if n_channels > 1:
            arr = arr.reshape(-1, n_channels).mean(axis=1)
        # 归一化到 [-1, 1]
        max_val = float(1 << (8 * sample_width - 1))
        arr /= max_val
        return arr, int(sr)
    except Exception as e:
        raise ValueError(f"无法解码音频(请提供 WAV 或安装 soundfile 解码 MP3 等): {e}")


def resample_linear(samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """线性插值重采样(无外部依赖)"""
    if src_sr == dst_sr or len(samples) == 0:
        return samples.astype(np.float32, copy=False)
    n_dst = int(round(len(samples) * dst_sr / src_sr))
    if n_dst <= 1:
        return samples.astype(np.float32, copy=False)
    idx = np.arange(n_dst, dtype=np.float32) * (src_sr / dst_sr)
    left = np.floor(idx).astype(np.int64)
    right = np.clip(left + 1, 0, len(samples) - 1)
    frac = idx - left
    out = samples[left] * (1.0 - frac) + samples[right] * frac
    return out.astype(np.float32, copy=False)


def to_pcm16(samples_f32: np.ndarray) -> bytes:
    """float32 [-1,1] -> int16 PCM bytes"""
    clipped = np.clip(samples_f32, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


def pcm16_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """int16 PCM bytes -> float32 [-1,1]"""
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    return arr / 32768.0


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int, num_channels: int = 1,
                     sample_width: int = 2) -> bytes:
    """将裸 PCM 封装为 WAV 字节"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()
