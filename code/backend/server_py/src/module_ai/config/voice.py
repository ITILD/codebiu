from pathlib import Path

from common.config.index import conf
from common.config.path import DIR_MODEL
import logging

logger = logging.getLogger(__name__)

# 语音模型根目录 temp_source/model/voice
DIR_VOICE_MODEL: Path = DIR_MODEL / "voice"

# 默认采样率
VOICE_DEFAULT_SAMPLE_RATE = 22050
# ASR 期望采样率(sherpa 流式识别固定 16kHz)
VOICE_ASR_SAMPLE_RATE = 16000

# 从 config.yaml 读取 voice 配置(可选，缺失时使用默认值)
try:
    conf_voice = conf.voice
    if conf_voice is None:
        conf_voice = {}
except Exception:
    conf_voice = {}

# ---------- sherpa 引擎配置 ----------
conf_voice_sherpa = conf_voice.get("sherpa", {}) if conf_voice else {}

# sherpa ASR 模型目录(在线流式 zipformer 中英双语)
SHERPA_ASR_MODEL_DIR: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "asr_model", "sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20"
)
SHERPA_ASR_TOKENS: Path = SHERPA_ASR_MODEL_DIR / conf_voice_sherpa.get("asr_tokens", "tokens.txt")

# sherpa TTS 模型(vits-melo-tts-zh_en)
SHERPA_TTS_MODEL: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "tts_model", "vits-melo-tts-zh_en/model.onnx"
)
SHERPA_TTS_TOKENS: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "tts_tokens", "vits-melo-tts-zh_en/tokens.txt"
)
SHERPA_TTS_LEXICON: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "tts_lexicon", "vits-melo-tts-zh_en/lexicon.txt"
)
SHERPA_TTS_DICT_DIR: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "tts_dict_dir", "vits-melo-tts-zh_en/dict"
)
# TTS 单次合成最长文本
SHERPA_TTS_MAX_NUM_SENTENCES: int = int(conf_voice_sherpa.get("max_num_sentences", 2))

# ---------- Qwen 引擎配置 ----------
conf_voice_qwen = conf_voice.get("qwen", {}) if conf_voice else {}

QWEN_ASR_MODEL_DIR: Path = DIR_VOICE_MODEL / conf_voice_qwen.get(
    "asr_model", "Qwen3-ASR-1.7B"
)
QWEN_TTS_MODEL_DIR: Path = DIR_VOICE_MODEL / conf_voice_qwen.get(
    "tts_model", "Qwen3-TTS-1.7B"
)
# Qwen 设备/cpu 线程
QWEN_DEVICE: str = conf_voice_qwen.get("device", "cpu")

logger.info("ok...voice 语音配置加载完成")
