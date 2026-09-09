"""语音活动检测(VAD)控制器

接口：
- POST /voice/vad    语音活动检测(切分语音段)

仅支持 sherpa(CPU) 实时方案(silero-vad), engine 参数缺省按模型配置自动选择。
"""
import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from module_ai.config.server import module_app
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import VADResponse, VoiceEngine
from module_ai.service.voice import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/vad",
    response_model=VADResponse,
    summary="语音活动检测(切分语音段)",
)
async def vad_detect(
    audio: UploadFile,
    engine: VoiceEngine | None = Form(None, description="VAD 引擎，缺省时按模型配置自动选择(仅 sherpa)"),
    voice_service: VoiceService = Depends(get_voice_service),
):
    """上传音频检测其中的语音段，返回各段的起止时间

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    start = time.time()
    segments = await voice_service.vad_segments(audio_bytes, engine)
    return VADResponse(segments=segments, elapsed=round(time.time() - start, 3))


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice", tags=["语音活动检测 VAD"])
