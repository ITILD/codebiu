"""语音服务(ASR/TTS/VAD/Denoise) 统一入口

引擎方案由 model_config 表驱动:
    - model_type=asr/tts/vad/denoise + server_type=sherpa/qwen 的记录即为可选方案
    - engine 参数可选: 指定时精确匹配 server_type, 缺省时取该类型第一条配置
    - 引擎缓存键含配置的 updated_at, 配置修改后自动重建引擎
    - 表中无配置时回落 config.yaml 的 voice 静态配置
"""
import logging
from typing import Iterator, Tuple

from module_ai.config.voice import VOICE_ASR_SAMPLE_RATE
from module_ai.dao.model_config import ModelConfigDao
from module_ai.do.model_config import ModelConfig
from module_ai.do.voice import VoiceEngine
from module_ai.utils.voice.asr import QwenASR, SherpaASR
from module_ai.utils.voice.denoise import SherpaDenoise
from module_ai.utils.voice.interface import ASREngine, DenoiseEngine, TTSEngine, VADEngine
from module_ai.utils.voice.tts import QwenTTS, SherpaTTS
from module_ai.utils.voice.vad import SherpaVAD

logger = logging.getLogger(__name__)

# 引擎类映射(model_type -> {server_type -> 类})
_ENGINE_CLASSES: dict[str, dict[str, type]] = {
    "asr": {VoiceEngine.SHERPA.value: SherpaASR, VoiceEngine.QWEN.value: QwenASR},
    "tts": {VoiceEngine.SHERPA.value: SherpaTTS, VoiceEngine.QWEN.value: QwenTTS},
    # vad/denoise 仅 sherpa(CPU) 方案
    "vad": {VoiceEngine.SHERPA.value: SherpaVAD},
    "denoise": {VoiceEngine.SHERPA.value: SherpaDenoise},
}


def _engine_conf(config: ModelConfig | None) -> dict:
    """ModelConfig -> 引擎配置字典(model/extra 展平)"""
    if config is None:
        return {}
    conf = dict(config.extra or {})
    # model 字段优先(extra 中可被显式覆盖)
    conf.setdefault("model", config.model)
    return conf


class VoiceService:
    """语音服务: 按模型配置选择 asr/tts 引擎方案"""

    def __init__(self, model_config_dao: ModelConfigDao | None = None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.model_config_dao = model_config_dao or ModelConfigDao()
        # 引擎缓存: (model_type, engine, cache_key) -> 引擎实例
        self._engines: dict[Tuple[str, VoiceEngine | None, str], ASREngine | TTSEngine] = {}

    async def _resolve_engine(
        self, model_type: str, engine: VoiceEngine | None
    ) -> ASREngine | TTSEngine:
        """
        查询 model_config 表并获取/构建引擎实例
        :param model_type: 模型类型(asr/tts)
        :param engine: 指定方案(None 时取第一条配置)
        :return: 引擎实例
        """
        # 查询该类型的模型配置(指定 engine 时按 server_type 精确匹配)
        config = await self.model_config_dao.get_first_by_type(
            model_type, server_type=engine.value if engine else None
        )
        # 实际生效的方案(未指定时取配置自身的 server_type; 无配置时回落 sherpa)
        effective = engine
        if config is not None:
            try:
                effective = VoiceEngine(config.server_type)
            except ValueError:
                effective = VoiceEngine.SHERPA
        elif effective is None:
            effective = VoiceEngine.SHERPA

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

    async def get_engine(self, model_type: str, engine: VoiceEngine | None = None) -> ASREngine | TTSEngine | VADEngine | DenoiseEngine:
        """按模型类型获取引擎实例(asr/tts/vad/denoise 通用)"""
        return await self._resolve_engine(model_type, engine)

    async def get_asr(self, engine: VoiceEngine | None = None) -> ASREngine:
        """
        获取 ASR 引擎(按模型配置选择方案)
        :param engine: 指定方案(None 时取第一条 asr 配置)
        """
        result = await self._resolve_engine("asr", engine)
        return result  # type: ignore[return-value]

    async def get_tts(self, engine: VoiceEngine | None = None) -> TTSEngine:
        """
        获取 TTS 引擎(按模型配置选择方案)
        :param engine: 指定方案(None 时取第一条 tts 配置)
        """
        result = await self._resolve_engine("tts", engine)
        return result  # type: ignore[return-value]

    async def asr(self, audio_bytes: bytes, engine: VoiceEngine | None = None) -> str:
        """语音识别(engine 为 None 时自动选择配置的方案)"""
        asr = await self.get_asr(engine)
        return asr.recognize(audio_bytes)

    async def tts(
        self,
        text: str,
        engine: VoiceEngine | None = None,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
    ) -> Tuple[bytes, int]:
        """语音合成(engine 为 None 时自动选择配置的方案)"""
        tts = await self.get_tts(engine)
        return tts.synthesize(text, speaker, speed, sample_rate)

    async def tts_stream(
        self,
        text: str,
        engine: VoiceEngine | None = None,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
    ) -> Tuple[Iterator[Tuple[bytes, int, bool]], VoiceEngine]:
        """
        流式语音合成
        :return: (PCM 分块迭代器, 实际生效的引擎)
        """
        # 先同步解析引擎(生成器内不能 await)
        tts = await self.get_tts(engine)
        # 计算实际生效的方案(用于响应头回显)
        effective = engine
        if effective is None:
            config = await self.model_config_dao.get_first_by_type("tts")
            try:
                effective = VoiceEngine(config.server_type) if config else VoiceEngine.SHERPA
            except ValueError:
                effective = VoiceEngine.SHERPA
        return tts.synthesize_stream(text, speaker, speed, sample_rate), effective

    async def get_vad(self, engine: VoiceEngine | None = None) -> VADEngine:
        """
        获取 VAD 引擎(实时语音活动检测, 仅 sherpa CPU 方案)
        :param engine: 指定方案(None 时取第一条 vad 配置)
        """
        result = await self._resolve_engine("vad", engine)
        return result  # type: ignore[return-value]

    async def get_denoise(self, engine: VoiceEngine | None = None) -> DenoiseEngine:
        """
        获取降噪引擎(实时语音降噪, 仅 sherpa CPU 方案)
        :param engine: 指定方案(None 时取第一条 denoise 配置)
        """
        result = await self._resolve_engine("denoise", engine)
        return result  # type: ignore[return-value]

    async def vad_segments(self, audio_bytes: bytes, engine: VoiceEngine | None = None) -> list[dict]:
        """对完整音频执行语音活动检测, 切分出全部语音段

        :return: [{"start": 起始秒, "duration": 时长秒}]
        """
        from module_ai.utils.voice.audio import load_audio, resample_linear

        vad = await self.get_vad(engine)
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

    async def denoise(self, audio_bytes: bytes, engine: VoiceEngine | None = None) -> tuple[bytes, int]:
        """对音频执行降噪

        :return: (降噪后 int16 PCM 字节, 采样率)
        """
        from module_ai.utils.voice.audio import load_audio

        denoiser = await self.get_denoise(engine)
        samples, sr = load_audio(audio_bytes)
        enhanced, out_sr = denoiser.enhance(samples, sr)
        from module_ai.utils.voice.audio import to_pcm16

        return to_pcm16(enhanced), out_sr
