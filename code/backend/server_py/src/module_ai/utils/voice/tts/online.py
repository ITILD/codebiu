"""在线(online) TTS 引擎

protocol 分派(配置 extra.protocol, 缺省 dashscope):
- dashscope: 百炼 CosyVoice 流式 WebSocket(逐块返回 PCM) / 非流式回退现有 HTTP 实现
- openai: OpenAI 兼容 /v1/audio/speech(本地 vllm 等发布端), 仅整段合成
"""
import logging
from collections.abc import AsyncIterator
from typing import Iterator, Tuple

from module_ai.utils.voice.dashscope_ws import DashscopeStreamTTS
from module_ai.utils.voice.interface import TTSEngine
from module_ai.utils.voice.tts.dashscope import DashscopeTTS

logger = logging.getLogger(__name__)

# OpenAI 兼容语音合成默认路径(vllm 等发布端按需覆盖 url)
_OPENAI_TTS_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/speech"


class OnlineTTS(TTSEngine):
    """在线(online) TTS 引擎: 远程 API 或本地 vllm 发布接口"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 引擎配置(model/url/api_key/extra), extra.protocol 分派协议
        """
        self._conf = conf or {}
        # extra(protocol/voice 等)已在 service._engine_conf 展平进 conf
        self._protocol = str(self._conf.get("protocol") or "dashscope")
        # 整段合成器(dashscope 复用现有 HTTP 实现; openai 走兼容接口)
        if self._protocol == "openai":
            self._sync_engine: TTSEngine = _OpenAICompatibleTTS(self._conf)
        else:
            self._sync_engine = DashscopeTTS(self._conf)

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        """整段合成完整音频(dashscope HTTP / openai 兼容接口)"""
        return self._sync_engine.synthesize(text, speaker, speed, sample_rate)

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[Tuple[bytes, int, bool]]:
        """同步流式(dashscope 整段切片; controller 优先走 synthesize_stream_async)"""
        yield from self._sync_engine.synthesize_stream(text, speaker, speed, sample_rate)

    async def synthesize_stream_async(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> AsyncIterator[Tuple[bytes, int, bool]]:
        """真流式: dashscope CosyVoice WebSocket 逐块返回音频(仅 dashscope 协议)"""
        if self._protocol != "dashscope":
            # openai 兼容端无流式: 线程池整段合成后切片返回
            import asyncio

            pcm, sr = await asyncio.to_thread(self.synthesize, text, speaker, speed, sample_rate)
            for chunk, out_sr, is_final in _slice_pcm(pcm, sr):
                yield chunk, out_sr, is_final
            return

        ws_conf = dict(self._conf)
        from module_ai.config.voice import VOICE_ONLINE_WS_URL

        ws_conf.setdefault("url", VOICE_ONLINE_WS_URL)
        ws_conf["rate"] = speed
        if speaker:
            ws_conf.setdefault("voice", str(speaker))
        stream = DashscopeStreamTTS(ws_conf)
        async for pcm_chunk, out_sr, is_final in stream.stream(text, sample_rate):
            yield pcm_chunk, out_sr, is_final


def _slice_pcm(pcm: bytes, sr: int, chunk_ms: int = 200) -> Iterator[Tuple[bytes, int, bool]]:
    """完整 PCM 按 200ms 切片流式产出(辅助函数)"""
    chunk_bytes = int(sr * chunk_ms / 1000) * 2
    offset = 0
    total = len(pcm)
    if total == 0:
        yield b"", sr, True
        return
    while offset < total:
        yield pcm[offset : offset + chunk_bytes], sr, offset + chunk_bytes >= total
        offset += chunk_bytes


class _OpenAICompatibleTTS(TTSEngine):
    """OpenAI 兼容语音合成(/v1/audio/speech, 本地 vllm 等发布端)"""

    def __init__(self, conf: dict):
        self._conf = conf

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("OpenAI 兼容 TTS 缺少 api_key: 请在模型配置中填写")
        return api_key

    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Tuple[bytes, int]:
        """POST JSON 请求音频字节, 解码为 PCM"""
        import httpx

        from module_ai.utils.voice.audio import load_audio, resample_linear, to_pcm16

        url = str(self._conf.get("url") or _OPENAI_TTS_URL)
        timeout = float(self._conf.get("timeout") or 60)
        payload = {
            "model": str(self._conf.get("model") or "qwen3-tts-flash"),
            "input": text,
            "voice": str(self._conf.get("voice") or "Cherry"),
            "response_format": "wav",
            "speed": max(0.5, min(2.0, speed)),
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    url, headers={"Authorization": f"Bearer {self._api_key}"}, json=payload
                )
        except httpx.HTTPError as e:
            raise RuntimeError(f"OpenAI 兼容 TTS 请求失败: {e}") from e
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI 兼容 TTS 请求失败({resp.status_code}): {resp.text[:500]}")
        samples, sr = load_audio(resp.content)
        if sr != sample_rate:
            samples = resample_linear(samples, sr, sample_rate)
            sr = sample_rate
        return to_pcm16(samples), sr
