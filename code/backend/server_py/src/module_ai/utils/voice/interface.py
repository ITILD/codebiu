from abc import ABC, abstractmethod
from typing import Generator, Iterator


class ASREngine(ABC):
    """ASR 引擎抽象接口"""

    @abstractmethod
    def recognize(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """离线识别完整音频，返回文本

        Args:
            audio_bytes: 音频原始字节(WAV/MP3 等可被 soundfile 解码的格式)
            sample_rate: 期望采样率
        """
        ...

    def create_stream(self):
        """创建一个在线流式识别会话，返回会话对象"""
        raise NotImplementedError("当前 ASR 引擎不支持流式识别")

    def stream_accept(self, stream, samples, sample_rate: int = 16000) -> str:
        """向流式会话送入一帧 PCM 样本，返回当前增量文本(可选)"""
        raise NotImplementedError("当前 ASR 引擎不支持流式识别")

    def stream_result(self, stream, is_final: bool = False) -> str:
        """获取流式会话的当前文本"""
        raise NotImplementedError("当前 ASR 引擎不支持流式识别")

    def stream_destroy(self, stream) -> None:
        """销毁流式会话"""
        pass


class TTSEngine(ABC):
    """TTS 引擎抽象接口"""

    @abstractmethod
    def synthesize(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> tuple[bytes, int]:
        """合成完整音频

        Returns:
            (pcm_int16_bytes, sample_rate)
        """
        ...

    def synthesize_stream(
        self, text: str, speaker: int = 0, speed: float = 1.0, sample_rate: int = 22050
    ) -> Iterator[tuple[bytes, int, bool]]:
        """流式合成音频，yield (pcm_int16_bytes, sample_rate, is_final)

        默认实现：先合成完整音频，再按 200ms 切片流式返回。
        子类可重写以实现真正的逐句流式合成。
        """
        pcm, sr = self.synthesize(text, speaker, speed, sample_rate)
        # 200ms 一片(int16 单声道)
        chunk_bytes = int(sr * 0.2) * 2
        total = len(pcm)
        offset = 0
        while offset < total:
            chunk = pcm[offset : offset + chunk_bytes]
            offset += chunk_bytes
            yield chunk, sr, offset >= total
