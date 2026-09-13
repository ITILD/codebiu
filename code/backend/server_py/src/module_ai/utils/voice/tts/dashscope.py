"""阿里云百炼(DashScope) 在线 TTS 引擎实现

通过 DashScope 非实时语音合成 HTTP 接口(CosyVoice/Qwen-Audio-TTS 系)合成语音,
非流式调用返回 24h 有效音频 URL, 引擎自动下载并解码为 PCM。

引擎配置来源优先级:
    1. model_config 表(model_type=tts, server_type=dashscope)的 model/url/api_key/extra 字段
    2. 类内默认值回落(cosyvoice-v2 + 官方接口地址)

extra 可选键:
    - voice: 音色 ID(如 longxiaochun/longanhuan_v3.6, 默认 longxiaochun)
    - language: 无需设置, 语种由文本自动判断
    - timeout: 请求超时秒数(默认 60)
"""
import logging
from typing import Iterator, Tuple

import httpx

from module_ai.utils.voice.audio import load_audio, resample_linear, to_pcm16
from module_ai.utils.voice.interface import TTSEngine

logger = logging.getLogger(__name__)

# DashScope 非实时语音合成接口(Qwen-Audio-TTS/CosyVoice)
_DASHSCOPE_TTS_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer"

# 默认请求超时(秒)
_DEFAULT_TIMEOUT = 60
# 服务端支持的采样率(取值范围文档限定)
_SUPPORTED_SAMPLE_RATES = (8000, 16000, 22050, 24000, 44100, 48000)
# 默认音色(CosyVoice 系统音色)
_DEFAULT_VOICE = "longxiaochun"


def _nearest_sample_rate(sample_rate: int) -> int:
    """将请求采样率映射到服务端支持的最近档位"""
    if sample_rate in _SUPPORTED_SAMPLE_RATES:
        return sample_rate
    return min(_SUPPORTED_SAMPLE_RATES, key=lambda sr: abs(sr - sample_rate))


class DashscopeTTS(TTSEngine):
    """阿里云在线 TTS 引擎(CosyVoice/Qwen-Audio-TTS, 非实时合成)"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 动态配置(model_config 映射), 可含:
            - model: 在线模型名(默认 cosyvoice-v2)
            - url: DashScope TTS 接口地址
            - api_key: 百炼 API Key(必填, 缺失时报错提示)
            - voice: 音色 ID(默认 longxiaochun)
            - timeout: 请求超时秒数
        """
        self._conf = conf or {}

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("DashScope TTS 缺少 api_key: 请在模型配置中填写百炼 API Key")
        return api_key

    def _synthesize_wav(self, text: str, speed: float, sample_rate: int) -> bytes:
        """调用合成接口, 返回 WAV 音频字节"""
        payload = {
            "model": str(self._conf.get("model") or "cosyvoice-v2"),
            "input": {
                "text": text,
                "voice": str(self._conf.get("voice") or _DEFAULT_VOICE),
                "format": "wav",
                "sample_rate": _nearest_sample_rate(sample_rate),
                "rate": max(0.5, min(2.0, speed)),
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        timeout = float(self._conf.get("timeout") or _DEFAULT_TIMEOUT)
        url = str(self._conf.get("url") or _DASHSCOPE_TTS_URL)
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code >= 400:
                    raise RuntimeError(f"DashScope TTS 请求失败({resp.status_code}): {resp.text[:500]}")
                result = resp.json()
                # 非流式响应: output.audio.url(24h 有效)或 output.audio.data(base64)
                audio = (result.get("output") or {}).get("audio") or {}
                if audio.get("data"):
                    import base64

                    return base64.b64decode(audio["data"])
                audio_url = audio.get("url")
                if not audio_url:
                    raise RuntimeError(f"DashScope TTS 未返回音频: {resp.text[:500]}")
                file_resp = client.get(audio_url)
                if file_resp.status_code >= 400:
                    raise RuntimeError(f"DashScope TTS 音频下载失败({file_resp.status_code})")
                return file_resp.content
        except httpx.HTTPError as e:
            raise RuntimeError(f"DashScope TTS 请求失败: {e}") from e

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        """合成完整音频并返回 (pcm_int16_bytes, sample_rate)

        :param speaker: 在线合成忽略(音色由 extra.voice 指定)
        """
        wav_bytes = self._synthesize_wav(text, speed, sample_rate)
        samples, sr = load_audio(wav_bytes)
        # 服务端返回采样率与请求不一致时重采样到目标采样率
        if sr != sample_rate:
            samples = resample_linear(samples, sr, sample_rate)
            sr = sample_rate
        return to_pcm16(samples), sr

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[Tuple[bytes, int, bool]]:
        """流式合成: 在线接口按整段返回, 复用基类切片实现"""
        yield from super().synthesize_stream(text, speaker, speed, sample_rate)
