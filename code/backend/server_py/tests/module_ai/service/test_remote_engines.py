# -*- coding: utf-8 -*-
"""module_ai 在线协议引擎(dashscope HTTP)标准测试

覆盖:
- 类型映射: server_types_for 对 asr/tts 返回 online/local, vad/denoise 仅 local, ocr dashscope/paddle
- 引擎归一化: 旧 engine 值 dashscope/sherpa/qwen -> online/local
- 引擎注册: VoiceService._ENGINE_CLASSES 含 online/local 引擎
- DashscopeASR/DashscopeTTS/DashscopeOCR: 请求体构建与响应解析(httpx 全局打桩, 零外部依赖)
- OCR 服务引擎解析: 无配置回落本地 paddle, dashscope 配置构建在线引擎并展平配置
"""

import base64
import json

import httpx
import numpy as np
import pytest

from module_ai.do.voice import resolve_engine
from module_ai.do.voice import VoiceEngine
from module_ai.service import voice as voice_service_mod
from module_ai.service.ocr import LOCAL_ENGINE, REMOTE_ENGINE, OcrService, _engine_conf
from module_ai.utils.llm.types import ModelServerType, ModelType, server_types_for
from module_ai.utils.ocr.dashscope import DashscopeOCR
from module_ai.utils.voice.asr.dashscope import DashscopeASR
from module_ai.utils.voice.asr.local import LocalASR
from module_ai.utils.voice.asr.online import OnlineASR
from module_ai.utils.voice.audio import pcm_to_wav_bytes, to_pcm16
from module_ai.utils.voice.tts.dashscope import DashscopeTTS
from module_ai.utils.voice.tts.local import LocalTTS
from module_ai.utils.voice.tts.online import OnlineTTS


# ==================== httpx 打桩(零外部依赖) ====================
class _FakeResponse:
    """httpx.Response 桩: 预设 JSON/二进制内容"""

    def __init__(self, payload: dict | None = None, content: bytes = b"", status_code: int = 200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code
        self.text = json.dumps(self._payload, ensure_ascii=False)

    def json(self) -> dict:
        return self._payload


class _FakeHttpClient:
    """httpx.Client 桩: 记录请求并按序返回预设响应(类属性 last 取最近实例)"""

    last: "_FakeHttpClient | None" = None

    def __init__(self, responses: list[_FakeResponse], **kwargs):
        self.responses = list(responses)
        self.calls: list[dict] = []
        type(self).last = self

    def __enter__(self) -> "_FakeHttpClient":
        return self

    def __exit__(self, *args) -> bool:
        return False

    def post(self, url: str, headers: dict | None = None, json: dict | None = None, **kw) -> _FakeResponse:
        self.calls.append({"method": "post", "url": url, "headers": headers, "json": json})
        return self.responses.pop(0)

    def get(self, url: str, **kw) -> _FakeResponse:
        self.calls.append({"method": "get", "url": url})
        return self.responses.pop(0)


def _patch_httpx(monkeypatch, responses: list[_FakeResponse]) -> None:
    """全局替换 httpx.Client 为打桩工厂(测试结束自动还原)"""
    monkeypatch.setattr(httpx, "Client", lambda **kw: _FakeHttpClient(responses, **kw))


# ==================== 类型映射与引擎注册 ====================
def test_server_types_for_remote_engines():
    """asr/tts 应返回 online/local 二值方案; ocr 保持 dashscope/paddle; vad/denoise 仅 local"""
    assert server_types_for(ModelType.ASR) == [ModelServerType.ONLINE, ModelServerType.LOCAL]
    assert server_types_for("tts") == [ModelServerType.ONLINE, ModelServerType.LOCAL]
    assert server_types_for("ocr") == [ModelServerType.DASHSCOPE, ModelServerType.PADDLE]
    # vad/denoise 仅本地方案(silero-vad / gtcrn onnx)
    assert server_types_for("vad") == [ModelServerType.LOCAL]
    assert server_types_for("denoise") == [ModelServerType.LOCAL]


def test_voice_engine_legacy_normalize():
    """旧 engine 值应自动归一化: dashscope->online, sherpa/qwen->local; 无效值回落 local"""
    assert resolve_engine("dashscope") is VoiceEngine.ONLINE
    assert resolve_engine("sherpa") is VoiceEngine.LOCAL
    assert resolve_engine("qwen") is VoiceEngine.LOCAL
    assert resolve_engine("online") is VoiceEngine.ONLINE
    assert resolve_engine("local") is VoiceEngine.LOCAL
    # 空值: 交由模型配置自动选择; 无效值: 回落 local(零外部依赖最稳)
    assert resolve_engine(None) is None
    assert resolve_engine("") is None
    assert resolve_engine("  ") is None
    assert resolve_engine("unknown-engine") is VoiceEngine.LOCAL


def test_voice_engine_classes_registered():
    """VoiceService 引擎类映射应注册 online/local 的 ASR/TTS 实现, vad/denoise 仅 local"""
    assert voice_service_mod._ENGINE_CLASSES["asr"][VoiceEngine.ONLINE.value] is OnlineASR
    assert voice_service_mod._ENGINE_CLASSES["asr"][VoiceEngine.LOCAL.value] is LocalASR
    assert voice_service_mod._ENGINE_CLASSES["tts"][VoiceEngine.ONLINE.value] is OnlineTTS
    assert voice_service_mod._ENGINE_CLASSES["tts"][VoiceEngine.LOCAL.value] is LocalTTS
    assert set(voice_service_mod._ENGINE_CLASSES["vad"]) == {VoiceEngine.LOCAL.value}
    assert set(voice_service_mod._ENGINE_CLASSES["denoise"]) == {VoiceEngine.LOCAL.value}


# ==================== DashscopeASR ====================
def test_dashscope_asr_recognize(monkeypatch):
    """ASR: base64 Data URL 上传 + 响应文本解析 + asr_options 参数透传"""
    _patch_httpx(
        monkeypatch,
        [_FakeResponse({"output": {"choices": [{"message": {"content": [{"text": "你好世界"}]}}]}})],
    )
    engine = DashscopeASR({"api_key": "sk-test", "language": "zh", "enable_itn": True})
    text = engine.recognize(b"RIFF0000WAVE", sample_rate=16000)
    assert text == "你好世界"

    call = _FakeHttpClient.last.calls[0]
    assert call["json"]["model"] == "qwen3-asr-flash"
    audio = call["json"]["input"]["messages"][0]["content"][0]["audio"]
    assert audio.startswith("data:audio/wav;base64,")
    assert call["json"]["parameters"]["asr_options"] == {"language": "zh", "enable_itn": True}
    assert call["headers"]["Authorization"] == "Bearer sk-test"


def test_dashscope_asr_missing_api_key():
    """ASR: 缺少 api_key 应给出可操作的错误提示(不发网络请求)"""
    with pytest.raises(RuntimeError, match="api_key"):
        DashscopeASR({}).recognize(b"RIFF0000WAVE")


def test_dashscope_asr_http_error(monkeypatch):
    """ASR: 服务端报错应抛出含状态码与响应体的 RuntimeError"""
    _patch_httpx(monkeypatch, [_FakeResponse({"error": "invalid key"}, status_code=401)])
    with pytest.raises(RuntimeError, match="401"):
        DashscopeASR({"api_key": "bad"}).recognize(b"RIFF0000WAVE")


# ==================== DashscopeTTS ====================
def _make_wav() -> bytes:
    """构造 22050Hz 的真实 WAV 字节(供打桩响应/解码验证)"""
    samples = (np.sin(np.linspace(0, 440 * 2 * np.pi, 2205)) * 0.5).astype("float32")
    return pcm_to_wav_bytes(to_pcm16(samples), 22050)


def test_dashscope_tts_synthesize(monkeypatch):
    """TTS: 非流式返回音频 URL 时自动下载并解码为 PCM"""
    wav_bytes = _make_wav()
    _patch_httpx(
        monkeypatch,
        [
            _FakeResponse({"output": {"audio": {"url": "https://example.com/a.wav"}}}),
            _FakeResponse(content=wav_bytes),
        ],
    )
    engine = DashscopeTTS({"api_key": "sk-test", "voice": "longxiaochun"})
    pcm, sr = engine.synthesize("你好", sample_rate=22050)
    assert sr == 22050
    assert len(pcm) > 0

    post, get = _FakeHttpClient.last.calls
    assert post["json"]["model"] == "cosyvoice-v2"
    assert post["json"]["input"]["voice"] == "longxiaochun"
    assert post["json"]["input"]["format"] == "wav"
    assert get["url"] == "https://example.com/a.wav"


def test_dashscope_tts_base64_data_fallback(monkeypatch):
    """TTS: 响应直接携带 base64 音频数据时无需二次下载"""
    wav_bytes = _make_wav()
    _patch_httpx(
        monkeypatch,
        [_FakeResponse({"output": {"audio": {"data": base64.b64encode(wav_bytes).decode()}}})],
    )
    pcm, sr = DashscopeTTS({"api_key": "sk-test"}).synthesize("hi", sample_rate=22050)
    assert sr == 22050
    assert len(pcm) > 0
    assert len(_FakeHttpClient.last.calls) == 1, "base64 数据路径不应再发起下载请求"


def test_dashscope_tts_missing_api_key():
    """TTS: 缺少 api_key 应给出可操作的错误提示"""
    with pytest.raises(RuntimeError, match="api_key"):
        DashscopeTTS({}).synthesize("你好")


# ==================== DashscopeOCR ====================
def test_dashscope_ocr_recognize(monkeypatch):
    """OCR: PNG Data URL 上传 + 结果与本地流水线同构(box 为整图矩形)"""
    _patch_httpx(
        monkeypatch,
        [_FakeResponse({"output": {"choices": [{"message": {"content": [{"text": "识别文本"}]}}]}})],
    )
    image = np.full((10, 20, 3), 255, dtype="uint8")
    result = DashscopeOCR({"api_key": "sk-test", "model": "qwen-vl-ocr-latest"}).recognize(image)
    assert result["results"][0]["text"] == "识别文本"
    assert result["results"][0]["box"] == [[0, 0], [20, 0], [20, 10], [0, 10]]
    assert result["results"][0]["score"] == 1.0
    assert result["engine"] == "dashscope"

    call = _FakeHttpClient.last.calls[0]
    assert call["json"]["model"] == "qwen-vl-ocr-latest"
    image_uri = call["json"]["input"]["messages"][0]["content"][0]["image"]
    assert image_uri.startswith("data:image/png;base64,")


def test_dashscope_ocr_missing_api_key():
    """OCR: 缺少 api_key 应给出可操作的错误提示"""
    with pytest.raises(RuntimeError, match="api_key"):
        DashscopeOCR({}).recognize(np.zeros((4, 4, 3), dtype="uint8"))


# ==================== OcrService 引擎解析 ====================
class _StubDao:
    """模型配置 DAO 桩: 返回预设配置, 不访问数据库"""

    def __init__(self, config):
        self._config = config

    async def get_first_by_type(self, model_type: str, session=None, server_type: str | None = None):
        if model_type != "ocr" or self._config is None:
            return None
        if server_type and self._config.server_type.value != server_type:
            return None
        return self._config


class _FakeConfig:
    """model_config 表记录桩(仅包含引擎解析所需字段)"""

    def __init__(self, server_type: ModelServerType):
        self.id = "cfg_1"
        self.updated_at = "2026-01-01"
        self.server_type = server_type
        self.model = "qwen-vl-ocr-latest"
        self.url = "https://dashscope.example.com/ocr"
        self.api_key = "sk-stub"
        self.extra = {"prompt": "read it"}


async def test_ocr_service_fallback_local():
    """无模型配置时应回落本地 paddle onnx 方案"""
    service = OcrService(model_config_dao=_StubDao(None))
    engine, remote = await service._resolve_engine(None)
    assert engine == LOCAL_ENGINE
    assert remote is None


async def test_ocr_service_dashscope_config():
    """dashscope 配置应构建在线引擎并展平 model/url/api_key/extra"""
    service = OcrService(model_config_dao=_StubDao(_FakeConfig(ModelServerType.DASHSCOPE)))
    engine, remote = await service._resolve_engine(None)
    assert engine == REMOTE_ENGINE
    assert isinstance(remote, DashscopeOCR)
    assert remote._conf["url"] == "https://dashscope.example.com/ocr"
    assert remote._conf["api_key"] == "sk-stub"
    assert remote._conf["prompt"] == "read it"


async def test_ocr_service_paddle_config():
    """paddle 配置应保持本地方案"""
    service = OcrService(model_config_dao=_StubDao(_FakeConfig(ModelServerType.PADDLE)))
    engine, remote = await service._resolve_engine(None)
    assert engine == LOCAL_ENGINE
    assert remote is None


def test_engine_conf_flatten():
    """_engine_conf 应以 model/url/api_key 为主字段, extra 值可显式覆盖"""
    conf = _engine_conf(_FakeConfig(ModelServerType.DASHSCOPE))
    assert conf["model"] == "qwen-vl-ocr-latest"
    assert conf["prompt"] == "read it"
    assert _engine_conf(None) == {}
