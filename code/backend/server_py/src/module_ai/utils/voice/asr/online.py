"""在线(online) ASR 引擎

protocol 分派(配置 extra.protocol, 缺省 dashscope):
- dashscope: 百炼原生接口(qwen3-asr-flash 整段识别 / paraformer-realtime·gummy 实时 WS 流式)
- openai: OpenAI 兼容 /v1/audio/transcriptions(本地 vllm 等发布), 仅离线识别

流式策略(混合):
- model 命中实时名单(voice.online.realtime_asr_models, 默认 paraformer-realtime/gummy)
  -> DashscopeRealtimeASRStream 真全双工 WS 流式
- 其余 -> PseudoStreamSession 伪流式: 缓冲 PCM, 按定长切片后台线程调同步接口, 累计拼接文本
"""
import concurrent.futures
import logging
import threading

from module_ai.utils.voice.asr.dashscope import DashscopeASR
from module_ai.utils.voice.audio import pcm_to_wav_bytes
from module_ai.utils.voice.dashscope_ws import DASHSCOPE_WS_URL, DashscopeRealtimeASRStream
from module_ai.utils.voice.interface import ASREngine

logger = logging.getLogger(__name__)

# OpenAI 兼容语音识别默认路径(vllm 等发布端按需覆盖 url)
_OPENAI_ASR_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/audio/transcriptions"


def _is_realtime_model(model: str, realtime_models: list[str]) -> bool:
    """判断模型名是否命中实时流式系列(前缀匹配, 如 paraformer-realtime-v2 命中 paraformer-realtime)"""
    return any(model.startswith(prefix) for prefix in realtime_models)


class PseudoStreamSession:
    """伪流式会话: 缓冲 PCM -> 定长切片后台识别 -> 累计拼接文本

    适用于仅提供整段同步接口的在线模型(qwen3-asr-flash 等)。
    识别在 ThreadPoolExecutor 中执行, 不阻塞事件循环。
    """

    def __init__(self, recognizer: ASREngine, sample_rate: int, chunk_seconds: float):
        """
        :param recognizer: 分片识别器(在线整段识别引擎)
        :param sample_rate: 音频采样率(16k)
        :param chunk_seconds: 切片时长(秒), 缓冲达到即提交后台识别
        """
        self._recognizer = recognizer
        self._sample_rate = sample_rate
        self._chunk_bytes = int(sample_rate * chunk_seconds) * 2  # int16 双字节
        self._buffer = bytearray()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="asr-pseudo")
        self._futures: list[concurrent.futures.Future] = []
        self._text = ""
        self._lock = threading.Lock()

    def accept(self, pcm_bytes: bytes) -> None:
        """缓冲音频帧, 达到切片阈值时提交后台识别"""
        with self._lock:
            self._buffer.extend(pcm_bytes)
            if len(self._buffer) >= self._chunk_bytes:
                chunk = bytes(self._buffer[: self._chunk_bytes])
                del self._buffer[: self._chunk_bytes]
                self._submit(chunk)

    def result(self, is_final: bool = False) -> str:
        """收割已完成切片的识别结果, 返回累计文本"""
        self._collect()
        return self._text

    def flush(self) -> None:
        """结束: 提交剩余缓冲并等待全部切片识别完成"""
        with self._lock:
            if self._buffer:
                chunk = bytes(self._buffer)
                self._buffer.clear()
                self._submit(chunk)
        self._collect(wait=True)

    def destroy(self) -> None:
        """销毁线程池"""
        self._executor.shutdown(wait=False)

    def _submit(self, pcm_chunk: bytes) -> None:
        """提交一个切片到线程池识别(PCM int16 -> WAV -> recognize)"""
        def _run() -> str:
            wav = pcm_to_wav_bytes(pcm_chunk, self._sample_rate)
            try:
                return self._recognizer.recognize(wav, self._sample_rate)
            except Exception as e:
                logger.warning(f"伪流式切片识别失败: {e}")
                return ""

        self._futures.append(self._executor.submit(_run))

    def _collect(self, wait: bool = False) -> None:
        """收割已完成的 future(可选等待全部), 顺序拼接文本"""
        done = []
        rest = []
        for fut in self._futures:
            if wait or fut.done():
                done.append(fut)
            else:
                rest.append(fut)
        for fut in done:
            try:
                piece = fut.result().strip()
            except Exception as e:
                logger.warning(f"伪流式切片结果获取失败: {e}")
                piece = ""
            if piece:
                # 切片边界可能出现重复字, 简单拼接即可(切片按静音/定长, 误差可接受)
                self._text = f"{self._text}{piece}"
        self._futures = rest


class OnlineASR(ASREngine):
    """在线(online) ASR 引擎: 远程 API 或本地 vllm 发布接口"""

    def __init__(self, conf: dict | None = None):
        """
        :param conf: 引擎配置(model/url/api_key/extra), extra.protocol 分派协议
        """
        self._conf = conf or {}
        # extra(protocol/engine 等)已在 service._engine_conf 展平进 conf
        self._protocol = str(self._conf.get("protocol") or "dashscope")
        # 整段同步识别器(dashscope 复用现有实现; openai 走兼容接口)
        if self._protocol == "openai":
            self._sync_engine = _OpenAICompatibleASR(self._conf)
        else:
            self._sync_engine = DashscopeASR(self._conf)

    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """离线识别完整音频(整段上传)"""
        return self._sync_engine.recognize(audio_bytes, sample_rate)

    def create_stream(self):
        """同步流式接口未实现(请使用 create_stream_async 异步会话)"""
        raise NotImplementedError("OnlineASR 请使用 create_stream_async 异步流式会话")

    async def create_stream_async(self):
        """创建流式会话: 实时系列走真 WS, 其余走伪流式"""
        from module_ai.config.voice import (
            VOICE_ONLINE_PSEUDO_CHUNK_SECONDS,
            VOICE_ONLINE_REALTIME_ASR_MODELS,
            VOICE_ONLINE_WS_URL,
        )

        model = str(self._conf.get("model") or "")
        if self._protocol == "dashscope" and _is_realtime_model(model, VOICE_ONLINE_REALTIME_ASR_MODELS):
            ws_conf = dict(self._conf)
            # 配置 url 为 REST 端点, WS 端点单独取默认值(仅 extra.ws_url 可覆盖)
            ws_conf["url"] = ws_conf.pop("ws_url", None) or VOICE_ONLINE_WS_URL
            stream = DashscopeRealtimeASRStream(ws_conf)
            await stream.start()
            return stream
        return PseudoStreamSession(
            self._sync_engine,
            sample_rate=int(self._conf.get("sample_rate") or 16000),
            chunk_seconds=VOICE_ONLINE_PSEUDO_CHUNK_SECONDS,
        )

    async def stream_accept_async(self, stream, samples, sample_rate: int = 16000) -> str:
        """送入一帧 PCM(兼容实时 WS 会话与伪流式会话两种形态)"""
        if isinstance(stream, DashscopeRealtimeASRStream):
            await stream.accept(samples)
            return ""
        if isinstance(stream, PseudoStreamSession):
            stream.accept(samples)
            return ""
        raise NotImplementedError("未知流式会话类型")

    async def stream_result_async(self, stream, is_final: bool = False) -> str:
        """获取当前识别文本(实时会话收割下行帧; 伪流式收割已完成切片)"""
        if isinstance(stream, DashscopeRealtimeASRStream):
            return await stream.text()
        if isinstance(stream, PseudoStreamSession):
            return stream.result(is_final)
        raise NotImplementedError("未知流式会话类型")

    async def stream_destroy_async(self, stream) -> None:
        """销毁会话(伪流式 flush 尾段; 实时会话 finish 并关连接)"""
        if isinstance(stream, DashscopeRealtimeASRStream):
            try:
                await stream.finish()
            finally:
                await stream.close()
            return
        if isinstance(stream, PseudoStreamSession):
            stream.flush()
            stream.destroy()
            return
        raise NotImplementedError("未知流式会话类型")


class _OpenAICompatibleASR(ASREngine):
    """OpenAI 兼容语音识别(/v1/audio/transcriptions, 本地 vllm 等发布端)"""

    def __init__(self, conf: dict):
        self._conf = conf

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("OpenAI 兼容 ASR 缺少 api_key: 请在模型配置中填写")
        return api_key

    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """multipart 上传音频文件识别"""
        import httpx

        url = str(self._conf.get("url") or _OPENAI_ASR_URL)
        timeout = float(self._conf.get("timeout") or 60)
        files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
        data = {"model": str(self._conf.get("model") or "qwen3-asr-flash")}
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    files=files,
                    data=data,
                )
        except httpx.HTTPError as e:
            raise RuntimeError(f"OpenAI 兼容 ASR 请求失败: {e}") from e
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI 兼容 ASR 请求失败({resp.status_code}): {resp.text[:500]}")
        return str(resp.json().get("text") or "").strip()
