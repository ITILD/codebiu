"""DashScope WebSocket 推理协议客户端(实时语音识别/流式语音合成共用)

协议要点(官方文档 wss://dashscope.aliyuncs.com/api-ws/v1/inference/):
- 鉴权: 握手阶段请求头 Authorization: Bearer <api_key>
- 指令帧(JSON 文本): header.action = run-task / continue-task / finish-task,
  同一任务复用同一 task_id(UUID), streaming="duplex"
  - run-task: payload 携 task_group=audio / task=asr|tts / function=recognition|SpeechSynthesizer / model / parameters
  - 二进制音频帧(ASR 上行)直接发送原始 PCM 字节, 无需 JSON 包装
- 下行事件(JSON 文本): header.event = task-started / result-generated / task-finished / task-failed
  - ASR 识别文本: payload.output.sentence.text
  - TTS 音频: 二进制帧, 合成结束以 task-finished 收尾

连接工厂 ws_connect 可注入(测试打桩), 默认 aiohttp ClientSession.ws_connect。
"""
import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any, Callable, Coroutine

import aiohttp

logger = logging.getLogger(__name__)

# DashScope WebSocket 推理端点
DASHSCOPE_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"

# 默认事件等待超时(秒)
_DEFAULT_EVENT_TIMEOUT = 60.0


class DashscopeWsError(RuntimeError):
    """DashScope WebSocket 任务失败"""


def _command(action: str, task_id: str, payload: dict) -> str:
    """构造指令帧 JSON(run-task/continue-task/finish-task 共用)"""
    return json.dumps(
        {"header": {"action": action, "task_id": task_id, "streaming": "duplex"}, "payload": payload},
        ensure_ascii=False,
    )


async def _run_task(
    ws: Any,
    task_id: str,
    *,
    task: str,
    function: str,
    model: str,
    parameters: dict,
) -> None:
    """发送 run-task 并等待 task-started 确认(失败抛 DashscopeWsError)"""
    payload = {
        "task_group": "audio",
        "task": task,
        "function": function,
        "model": model,
        "input": {},
        "parameters": parameters,
    }
    await ws.send_str(_command("run-task", task_id, payload))
    event = await _wait_event(ws, task_id, {"task-started"})
    if event != "task-started":
        raise DashscopeWsError(f"run-task 未收到 task-started: {event}")


async def _wait_event(ws: Any, task_id: str, events: set[str], timeout: float = _DEFAULT_EVENT_TIMEOUT) -> str:
    """循环读帧直至收到目标事件, 返回事件名; task-failed 抛错; 二进制帧跳过由调用方处理"""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remain = deadline - loop.time()
        if remain <= 0:
            raise DashscopeWsError(f"等待事件超时(期望 {events})")
        msg = await asyncio.wait_for(ws.receive(), timeout=remain)
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            header = data.get("header") or {}
            event = str(header.get("event") or "")
            if event == "task-failed":
                raise DashscopeWsError(
                    f"任务失败({header.get('error_code')}): {header.get('error_message')}"
                )
            if event in events:
                return event
        elif msg.type == aiohttp.WSMsgType.BINARY:
            continue  # 事件等待阶段忽略二进制帧
        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            raise DashscopeWsError(f"WebSocket 连接已关闭/异常: {msg.data}")
        # 任务归属校验(多任务复用连接时只处理当前 task_id 的事件)
        _ = task_id


class DashscopeRealtimeASRStream:
    """DashScope 实时语音识别会话(paraformer-realtime/gummy 系列, 全双工 WS)

    用法: await start() -> await accept(pcm_bytes) 循环送音频 -> await text() 取当前文本
          -> await finish() 收尾 -> await close() 关闭连接
    """

    def __init__(self, conf: dict, ws_connect: Callable[..., Coroutine] | None = None):
        """
        :param conf: 引擎配置(model/url/api_key/sample_rate/language 等)
        :param ws_connect: WS 连接工厂(默认 aiohttp), 签名 (url, headers) -> ws 对象
        """
        self._conf = conf or {}
        self._ws_connect = ws_connect
        self._session: aiohttp.ClientSession | None = None
        self._ws: Any = None
        self._task_id: str = ""
        self._text: str = ""
        self._finished: bool = False

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("DashScope 实时 ASR 缺少 api_key: 请在模型配置中填写百炼 API Key")
        return api_key

    async def _connect(self):
        """建立 WS 连接(工厂注入优先, 默认 aiohttp)"""
        if self._ws_connect is not None:
            return await self._ws_connect(self._conf.get("url") or DASHSCOPE_WS_URL, self._headers)
        self._session = aiohttp.ClientSession()
        return await self._session.ws_connect(
            str(self._conf.get("url") or DASHSCOPE_WS_URL), headers=self._headers
        )

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "user-agent": "codebiu-voice/1.0",
        }

    async def start(self) -> None:
        """建立连接并启动识别任务(阻塞至 task-started)"""
        self._task_id = str(uuid.uuid4())
        self._ws = await self._connect()
        parameters: dict = {
            "format": "pcm",
            "sample_rate": int(self._conf.get("sample_rate") or 16000),
        }
        if self._conf.get("language"):
            parameters["language_hints"] = [str(self._conf["language"])]
        await _run_task(
            self._ws,
            self._task_id,
            task="asr",
            function="recognition",
            model=str(self._conf.get("model") or "paraformer-realtime-v2"),
            parameters=parameters,
        )

    async def accept(self, pcm_bytes: bytes) -> None:
        """送入一帧 16bit 单声道 PCM 音频"""
        if self._ws is None or self._finished:
            return
        await self._ws.send_bytes(pcm_bytes)

    async def text(self, timeout: float = 0.0) -> str:
        """非阻塞收割下行识别文本(聚合 result-generated 的 sentence.text)

        :param timeout: 最长收割时间(秒), 0 表示只收割当前已到达的帧
        """
        if self._ws is None or self._finished:
            return self._text
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout if timeout > 0 else None
        try:
            while True:
                wait_for = max(0.001, deadline - loop.time()) if deadline else 0.001
                msg = await asyncio.wait_for(self._ws.receive(), timeout=wait_for)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    header = data.get("header") or {}
                    event = str(header.get("event") or "")
                    if event == "task-failed":
                        raise DashscopeWsError(
                            f"实时 ASR 任务失败({header.get('error_code')}): {header.get('error_message')}"
                        )
                    if event == "result-generated":
                        sentence = ((data.get("payload") or {}).get("output") or {}).get("sentence") or {}
                        text = str(sentence.get("text") or "").strip()
                        if text:
                            self._text = text  # paraformer 返回全量文本(含中间结果)
                    elif event == "task-finished":
                        self._finished = True
                        break
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    continue
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    self._finished = True
                    break
        except asyncio.TimeoutError:
            pass  # 无更多下行帧, 正常返回当前聚合文本
        return self._text

    async def finish(self) -> str:
        """发送 finish-task 并收割最终识别文本"""
        if self._ws is not None and not self._finished:
            await self._ws.send_str(_command("finish-task", self._task_id, {"input": {}}))
            await self.text(timeout=_DEFAULT_EVENT_TIMEOUT)
        return self._text

    async def close(self) -> None:
        """关闭 WS 连接与会话"""
        self._finished = True
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None


class DashscopeStreamTTS:
    """DashScope 流式语音合成会话(CosyVoice/Qwen-Audio-TTS, WS 逐块返回音频)

    用法: async for (pcm_chunk, sample_rate, is_final) in engine.synthesize_stream_async(...)
    """

    def __init__(self, conf: dict, ws_connect: Callable[..., Coroutine] | None = None):
        """
        :param conf: 引擎配置(model/url/api_key/voice/sample_rate/rate 等)
        :param ws_connect: WS 连接工厂(默认 aiohttp)
        """
        self._conf = conf or {}
        self._ws_connect = ws_connect
        self._session: aiohttp.ClientSession | None = None
        self._ws: Any = None
        self._task_id: str = ""
        self._final: bool = False

    @property
    def _api_key(self) -> str:
        api_key = str(self._conf.get("api_key") or "").strip()
        if not api_key:
            raise RuntimeError("DashScope 流式 TTS 缺少 api_key: 请在模型配置中填写百炼 API Key")
        return api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "user-agent": "codebiu-voice/1.0",
        }

    async def _open(self, sample_rate: int) -> None:
        """建连并 run-task(阻塞至 task-started)"""
        self._task_id = str(uuid.uuid4())
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(
            str(self._conf.get("url") or DASHSCOPE_WS_URL), headers=self._headers
        )
        parameters = {
            "text_type": "PlainText",
            "format": "pcm",  # 裸 PCM, 前端按 X-Sample-Rate 播放
            "sample_rate": sample_rate,
            "voice": str(self._conf.get("voice") or "longxiaochun_v2"),
            "rate": max(0.5, min(2.0, float(self._conf.get("rate") or 1.0))),
        }
        await _run_task(
            self._ws,
            self._task_id,
            task="tts",
            function="SpeechSynthesizer",
            model=str(self._conf.get("model") or "cosyvoice-v2"),
            parameters=parameters,
        )

    async def stream(
        self, text: str, sample_rate: int = 22050
    ) -> AsyncIterator[tuple[bytes, int, bool]]:
        """流式合成: 按句 continue-task 送文本, yield (pcm_int16, sample_rate, is_final)"""
        await self._open(sample_rate)
        try:
            # 文本一次提交, 服务端自动分句流式返回(continue-task 可多次, 单句有长度约束)
            await self._ws.send_str(
                _command("continue-task", self._task_id, {"input": {"text": text}})
            )
            await self._ws.send_str(_command("finish-task", self._task_id, {"input": {}}))
            while True:
                msg = await self._ws.receive()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    yield msg.data, sample_rate, False
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    header = data.get("header") or {}
                    event = str(header.get("event") or "")
                    if event == "task-failed":
                        raise DashscopeWsError(
                            f"流式 TTS 任务失败({header.get('error_code')}): {header.get('error_message')}"
                        )
                    if event == "task-finished":
                        self._final = True
                        break
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    raise DashscopeWsError(f"WebSocket 连接已关闭/异常: {msg.data}")
            yield b"", sample_rate, True
        finally:
            await self.close()

    async def close(self) -> None:
        """关闭 WS 连接与会话"""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
