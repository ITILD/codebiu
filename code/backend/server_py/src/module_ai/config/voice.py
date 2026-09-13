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
# VAD 检测采样率(silero-vad 固定 16kHz)
VOICE_VAD_SAMPLE_RATE = 16000

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

# sherpa VAD 模型(silero-vad, CPU 实时语音活动检测)
SHERPA_VAD_MODEL: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "vad_model", "silero_vad.onnx"
)
# sherpa 降噪模型(GTCRN, CPU 实时语音降噪)
SHERPA_DENOISE_MODEL: Path = DIR_VOICE_MODEL / conf_voice_sherpa.get(
    "denoise_model", "gtcrn_simple.onnx"
)

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

# ---------- Online 引擎配置(远程API或本地vllm发布) ----------
conf_voice_online = conf_voice.get("online", {}) if conf_voice else {}

# DashScope WebSocket 推理端点(实时 ASR / 流式 TTS 共用)
VOICE_ONLINE_WS_URL: str = conf_voice_online.get(
    "ws_url", "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
)
# 命中实时系列的模型名前缀(走真 WS 流式), 其余在线模型走伪流式(缓冲切片调同步接口)
VOICE_ONLINE_REALTIME_ASR_MODELS: list[str] = list(
    conf_voice_online.get("realtime_asr_models", ["paraformer-realtime", "gummy"])
)
# 伪流式切片时长(秒): 缓冲达到该时长即提交后台识别
VOICE_ONLINE_PSEUDO_CHUNK_SECONDS: float = float(conf_voice_online.get("pseudo_chunk_seconds", 2.5))

logger.info("ok...voice 语音配置加载完成")
