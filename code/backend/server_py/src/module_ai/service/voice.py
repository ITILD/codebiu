"""语音服务(ASR/TTS/VAD/Denoise) 统一入口

引擎方案由 model_config 表驱动:
    - model_type=asr/tts/vad/denoise + server_type=online/local 的记录即为可选方案
    - engine 参数可选: 指定时精确匹配 server_type(旧值 dashscope/sherpa/qwen 自动归一化), 缺省时取该类型第一条配置
    - 引擎缓存键含配置的 updated_at, 配置修改后自动重建引擎
    - 表中无配置时回落 config.yaml 的 voice 静态配置(local sherpa 本地方案)
    - online/local 内部细节由 extra 分派: extra.protocol=dashscope|openai / extra.engine=sherpa|qwen
"""
import logging
from collections.abc import AsyncIterator
from typing import Iterator, Tuple

from module_ai.config.voice import VOICE_ASR_SAMPLE_RATE
from module_ai.dao.model_config import ModelConfigDao
from module_ai.do.model_config import ModelConfig
from module_ai.do.voice import VoiceEngine
from module_ai.utils.voice.asr import LocalASR, OnlineASR
from module_ai.utils.voice.denoise import SherpaDenoise
from module_ai.utils.voice.interface import ASREngine, DenoiseEngine, TTSEngine, VADEngine
from module_ai.utils.voice.tts import LocalTTS, OnlineTTS
from module_ai.utils.voice.vad import SherpaVAD

logger = logging.getLogger(__name__)

# 引擎类映射(model_type -> {server_type -> 类})
_ENGINE_CLASSES: dict[str, dict[str, type]] = {
    "asr": {
        VoiceEngine.ONLINE.value: OnlineASR,
        VoiceEngine.LOCAL.value: LocalASR,
    },
    "tts": {
        VoiceEngine.ONLINE.value: OnlineTTS,
        VoiceEngine.LOCAL.value: LocalTTS,
    },
    # vad/denoise 仅 local(sherpa onnx) 方案
    "vad": {VoiceEngine.LOCAL.value: SherpaVAD},
    "denoise": {VoiceEngine.LOCAL.value: SherpaDenoise},
}


def _engine_conf(config: ModelConfig | None) -> dict:
    """ModelConfig -> 引擎配置字典(extra 展平, model 字段优先)"""
    if config is None:
        return {}
    conf = dict(config.extra or {})
    # model 字段优先(extra 中可被显式覆盖)
    conf.setdefault("model", config.model)
    return conf


class VoiceService:
    """语音服务: 按模型配置选择 asr/tts 引擎方案(支持用户级个人绑定)"""

    def __init__(self, model_config_dao: ModelConfigDao | None = None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.model_config_dao = model_config_dao or ModelConfigDao()
        # 引擎缓存: (model_type, engine, cache_key) -> 引擎实例
        self._engines: dict[Tuple[str, VoiceEngine | None, str], ASREngine | TTSEngine] = {}

    async def _resolve_user_config(self, model_type: str, user_id: str | None) -> ModelConfig | None:
        """解析用户级语音模型配置(个人绑定 → 默认公共模型; 延迟导入避免与 module_rag 循环依赖)

        :param model_type: 模型类型(asr/tts/vad/denoise)
        :param user_id: 当前用户ID(None 按未绑定处理)
        :return: 用户可用的模型配置, 无绑定/无权限/异常时返回 None(交由调用方回落全局方案)
        """
        if not user_id:
            return None
        try:
            from module_ai.utils.llm.types import ModelType
            from module_rag.service.user_model import UserModelService

            resolved = await UserModelService().resolve_model(user_id, ModelType(model_type))
            if resolved.model_id is None:
                return None
            return await self.model_config_dao.get(resolved.model_id)
        except Exception as e:
            logger.warning(f"解析用户 {user_id} 的 {model_type} 模型绑定失败, 按未绑定处理: {e}")
            return None

    async def _resolve_engine(
        self, model_type: str, engine: VoiceEngine | None, user_id: str | None = None
    ) -> ASREngine | TTSEngine:
        """
        查询 model_config 表并获取/构建引擎实例
        :param model_type: 模型类型(asr/tts/vad/denoise)
        :param engine: 指定方案(None 时按用户绑定/全局配置自动选择)
        :param user_id: 当前用户ID(用户绑定优先于全局配置)
        :return: 引擎实例
        """
        # 指定 engine 时按 server_type 精确匹配; 未指定时优先用户绑定, 再回落全局配置
        if engine is not None:
            config = await self.model_config_dao.get_first_by_type(
                model_type, server_type=engine.value
            )
        else:
            config = await self._resolve_user_config(model_type, user_id)
            if config is None:
                config = await self.model_config_dao.get_first_by_type(model_type)
        # 实际生效的方案(未指定时取配置自身的 server_type; 无配置时回落 local)
        effective = engine
        if config is not None:
            try:
                effective = VoiceEngine(config.server_type)
            except ValueError:
                effective = VoiceEngine.LOCAL
        elif effective is None:
            effective = VoiceEngine.LOCAL

        # 缓存键: 配置ID + updated_at(配置变更自动失效)
        cache_key = "static"
        if config is not None:
            cache_key = f"{config.id}:{config.updated_at}"

        key = (model_type, effective, cache_key)
        if key not in self._engines:
            engine_cls = _ENGINE_CLASSES[model_type][effective.value]
            self._engines[key] = engine_cls(_engine_conf(config))
            logger.info("语音引擎已构建: %s/%s (来源: %s)", model_type, effective.value, cache_key)
        return self._engines[key]

    async def get_engine(
        self, model_type: str, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> ASREngine | TTSEngine | VADEngine | DenoiseEngine:
        """按模型类型获取引擎实例(asr/tts/vad/denoise 通用)"""
        return await self._resolve_engine(model_type, engine, user_id)

    async def get_asr(
        self, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> ASREngine:
        """
        获取 ASR 引擎(按用户绑定/模型配置选择方案)
        :param engine: 指定方案(None 时自动选择)
        :param user_id: 当前用户ID(用户绑定优先)
        """
        result = await self._resolve_engine("asr", engine, user_id)
        return result  # type: ignore[return-value]

    async def get_tts(
        self, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> TTSEngine:
        """
        获取 TTS 引擎(按用户绑定/模型配置选择方案)
        :param engine: 指定方案(None 时自动选择)
        :param user_id: 当前用户ID(用户绑定优先)
        """
        result = await self._resolve_engine("tts", engine, user_id)
        return result  # type: ignore[return-value]

    async def asr(
        self, audio_bytes: bytes, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> str:
        """语音识别(未指定 engine 时按用户绑定/全局配置自动选择方案)"""
        asr = await self.get_asr(engine, user_id)
        return asr.recognize(audio_bytes)

    async def asr_preprocess(
        self,
        audio_bytes: bytes,
        steps: list[str],
        engine: VoiceEngine | None = None,
        user_id: str | None = None,
    ) -> str:
        """带前置处理的语音识别管线: denoise(降噪) -> vad(切段) -> 逐段识别 -> 合并

        :param steps: 前置步骤列表(支持 "denoise"/"vad" 任意组合, 顺序固定为 denoise 先于 vad)
        :return: 合并后的识别文本
        """
        from module_ai.utils.voice.audio import load_audio, resample_linear

        samples, sr = load_audio(audio_bytes)
        if sr != VOICE_ASR_SAMPLE_RATE:
            samples = resample_linear(samples, sr, VOICE_ASR_SAMPLE_RATE)

        # 步骤1: 降噪(仅 local 方案可用)
        if "denoise" in steps:
            denoiser = await self.get_denoise(user_id=user_id)
            samples, sr = denoiser.enhance(samples, sr)

        # 无 vad: 处理后音频整段直接识别
        if "vad" not in steps:
            return await self.asr(_seg_wav(samples), engine, user_id)

        # 步骤2: VAD 切段 -> 逐段识别 -> 按序合并
        vad = await self.get_vad(user_id=user_id)
        vad.accept_waveform(samples)
        vad.flush()
        texts: list[str] = []
        try:
            while vad.is_speech_detected():
                segment = vad.pop_speech_segment()
                if segment is None:
                    break
                seg, _start = segment
                wav = _seg_wav(seg)
                text = await self.asr(wav, engine, user_id)
                if text.strip():
                    texts.append(text.strip())
        finally:
            vad.reset()
        return "".join(texts)

    async def tts(
        self,
        text: str,
        engine: VoiceEngine | None = None,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
        user_id: str | None = None,
    ) -> Tuple[bytes, int]:
        """语音合成(未指定 engine 时按用户绑定/全局配置自动选择方案)"""
        tts = await self.get_tts(engine, user_id)
        return tts.synthesize(text, speaker, speed, sample_rate)

    async def tts_stream(
        self,
        text: str,
        engine: VoiceEngine | None = None,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
        user_id: str | None = None,
    ) -> Tuple[Iterator[Tuple[bytes, int, bool]], VoiceEngine]:
        """
        流式语音合成(同步 iterator 路径)
        :return: (PCM 分块迭代器, 实际生效的引擎)
        """
        # 先同步解析引擎(生成器内不能 await)
        tts = await self.get_tts(engine, user_id)
        effective = await self._effective_engine("tts", engine, user_id)
        return tts.synthesize_stream(text, speaker, speed, sample_rate), effective

    async def tts_stream_async(
        self,
        text: str,
        engine: VoiceEngine | None = None,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
        user_id: str | None = None,
    ) -> Tuple[AsyncIterator[Tuple[bytes, int, bool]] | Iterator[Tuple[bytes, int, bool]], VoiceEngine, bool]:
        """
        流式语音合成(优先真异步路径)
        :return: (分块迭代器[Async|Sync], 实际生效引擎, 是否异步迭代器)
        """
        tts = await self.get_tts(engine, user_id)
        effective = await self._effective_engine("tts", engine, user_id)
        # 异步生成器函数调用时不会执行方法体, NotImplementedError 要到首个 __anext__ 才抛出,
        # 因此通过"是否覆写基类方法"判断真异步支持(如 LocalTTS 未覆写则回退同步切片路径)
        if type(tts).synthesize_stream_async is not TTSEngine.synthesize_stream_async:
            return tts.synthesize_stream_async(text, speaker, speed, sample_rate), effective, True
        return tts.synthesize_stream(text, speaker, speed, sample_rate), effective, False

    async def _effective_engine(
        self, model_type: str, engine: VoiceEngine | None, user_id: str | None = None
    ) -> VoiceEngine:
        """计算实际生效方案(用户绑定 → 全局配置自身方案; 无配置时回落 local)"""
        if engine is not None:
            return engine
        config = await self._resolve_user_config(model_type, user_id)
        if config is None:
            config = await self.model_config_dao.get_first_by_type(model_type)
        try:
            return VoiceEngine(config.server_type) if config else VoiceEngine.LOCAL
        except ValueError:
            return VoiceEngine.LOCAL

    async def get_vad(
        self, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> VADEngine:
        """
        获取 VAD 引擎(实时语音活动检测, 仅 local sherpa onnx 方案)
        :param engine: 指定方案(None 时按用户绑定/模型配置自动选择)
        :param user_id: 当前用户ID(用户绑定优先)
        """
        result = await self._resolve_engine("vad", engine, user_id)
        return result  # type: ignore[return-value]

    async def get_denoise(
        self, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> DenoiseEngine:
        """
        获取降噪引擎(实时语音降噪, 仅 local sherpa onnx 方案)
        :param engine: 指定方案(None 时按用户绑定/模型配置自动选择)
        :param user_id: 当前用户ID(用户绑定优先)
        """
        result = await self._resolve_engine("denoise", engine, user_id)
        return result  # type: ignore[return-value]

    async def vad_segments(
        self, audio_bytes: bytes, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> list[dict]:
        """对完整音频执行语音活动检测, 切分出全部语音段

        :return: [{"start": 起始秒, "duration": 时长秒}]
        """
        from module_ai.utils.voice.audio import load_audio, resample_linear

        vad = await self.get_vad(engine, user_id)
        samples, sr = load_audio(audio_bytes)
        if sr != VOICE_ASR_SAMPLE_RATE:
            samples = resample_linear(samples, sr, VOICE_ASR_SAMPLE_RATE)
        vad.accept_waveform(samples)
        vad.flush()
        segments = []
        while vad.is_speech_detected():
            segment = vad.pop_speech_segment()
            if segment is None:
                break
            seg, start = segment
            segments.append({
                "start": round(start / VOICE_ASR_SAMPLE_RATE, 3),
                "duration": round(len(seg) / VOICE_ASR_SAMPLE_RATE, 3),
            })
        vad.reset()
        return segments

    async def denoise(
        self, audio_bytes: bytes, engine: VoiceEngine | None = None, user_id: str | None = None
    ) -> tuple[bytes, int]:
        """对音频执行降噪

        :return: (降噪后 int16 PCM 字节, 采样率)
        """
        from module_ai.utils.voice.audio import load_audio

        denoiser = await self.get_denoise(engine, user_id)
        samples, sr = load_audio(audio_bytes)
        enhanced, out_sr = denoiser.enhance(samples, sr)
        from module_ai.utils.voice.audio import to_pcm16

        return to_pcm16(enhanced), out_sr


def _seg_wav(seg) -> bytes:
    """语音段 float32 样本 -> WAV 字节(供逐段识别)"""
    from module_ai.utils.voice.audio import pcm_to_wav_bytes, to_pcm16

    return pcm_to_wav_bytes(to_pcm16(seg), VOICE_ASR_SAMPLE_RATE)
