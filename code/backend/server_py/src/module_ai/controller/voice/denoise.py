"""语音降噪(Denoise)控制器

接口：
- POST /voice/denoise    语音降噪(返回降噪后 wav)

仅支持 sherpa(CPU) 实时方案(GTCRN), engine 参数缺省按模型配置自动选择。
"""
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status

from module_ai.config.server import module_app
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import VoiceEngine
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio import pcm_to_wav_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/denoise",
    summary="语音降噪(返回降噪后音频)",
)
async def denoise_audio(
    audio: UploadFile,
    engine: VoiceEngine | None = Form(None, description="降噪引擎，缺省时按模型配置自动选择(仅 sherpa)"),
    voice_service: VoiceService = Depends(get_voice_service),
):
    """上传含噪音频执行降噪，返回降噪后的 WAV 音频

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    pcm, sr = await voice_service.denoise(audio_bytes, engine)
    wav_bytes = pcm_to_wav_bytes(pcm, sr)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sr)},
    )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice", tags=["语音降噪 Denoise"])
