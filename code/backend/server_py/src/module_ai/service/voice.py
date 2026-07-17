"""语音服务(ASR/TTS) 统一入口，支持 sherpa / qwen 引擎切换"""
import logging
from typing import Iterator, Tuple

from module_ai.do.voice import VoiceEngine
from module_ai.utils.voice.interface import ASREngine, TTSEngine
from module_ai.utils.voice.qwen_asr import QwenASR
from module_ai.utils.voice.qwen_tts import QwenTTS
from module_ai.utils.voice.sherpa_asr import SherpaASR
from module_ai.utils.voice.sherpa_tts import SherpaTTS

logger = logging.getLogger(__name__)


class VoiceService:
    """语音服务：根据 engine 参数切换 sherpa / qwen 引擎"""

    def __init__(self):
        self._asr: dict[VoiceEngine, ASREngine | None] = {
            VoiceEngine.SHERPA: None,
            VoiceEngine.QWEN: None,
        }
        self._tts: dict[VoiceEngine, TTSEngine | None] = {
            VoiceEngine.SHERPA: None,
            VoiceEngine.QWEN: None,
        }

    def get_asr(self, engine: VoiceEngine) -> ASREngine:
        if self._asr[engine] is None:
            if engine == VoiceEngine.SHERPA:
                self._asr[engine] = SherpaASR()
            else:
                self._asr[engine] = QwenASR()
        return self._asr[engine]

    def get_tts(self, engine: VoiceEngine) -> TTSEngine:
        if self._tts[engine] is None:
            if engine == VoiceEngine.SHERPA:
                self._tts[engine] = SherpaTTS()
            else:
                self._tts[engine] = QwenTTS()
        return self._tts[engine]

    def asr(self, audio_bytes: bytes, engine: VoiceEngine = VoiceEngine.SHERPA) -> str:
        return self.get_asr(engine).recognize(audio_bytes)

    def tts(
        self,
        text: str,
        engine: VoiceEngine = VoiceEngine.SHERPA,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
    ) -> Tuple[bytes, int]:
        return self.get_tts(engine).synthesize(text, speaker, speed, sample_rate)

    def tts_stream(
        self,
        text: str,
        engine: VoiceEngine = VoiceEngine.SHERPA,
        speaker: int = 0,
        speed: float = 1.0,
        sample_rate: int = 22050,
    ) -> Iterator[Tuple[bytes, int, bool]]:
        return self.get_tts(engine).synthesize_stream(text, speaker, speed, sample_rate)
