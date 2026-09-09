"""语音合成(TTS)控制器

接口：
- POST /voice/tts/file    语音合成(返回完整音频文件 wav)
- POST /voice/tts/stream  语音合成(流式返回 PCM)

engine 参数可选：缺省时按模型配置(model_config 表 model_type=tts)自动选择方案。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from module_ai.config.server import module_app
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import TTSRequest
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio import pcm_to_wav_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/tts/file",
    summary="语音合成(返回完整音频文件)",
)
async def tts_file(
    req: TTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
):
    """文本合成语音，返回完整 WAV 音频文件

    - **text**: 待合成文本
    - **engine**: 引擎 sherpa / qwen(缺省按模型配置自动选择)
    """
    if not req.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文本内容为空")
    pcm, sr = await voice_service.tts(
        req.text,
        req.engine,
        req.speaker,
        req.speed,
        req.sample_rate,
    )

    wav_bytes = pcm_to_wav_bytes(pcm, sr)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=tts.wav",
            "X-Sample-Rate": str(sr),
        },
    )


@router.post(
    "/tts/stream",
    summary="语音合成(流式返回 PCM)",
)
async def tts_stream(
    req: TTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
):
    """文本合成语音，流式返回裸 PCM(16bit 单声道)

    通过响应头 X-Sample-Rate 返回采样率，客户端可边收边播。
    - **text**: 待合成文本
    - **engine**: 引擎 sherpa / qwen(缺省按模型配置自动选择)
    """
    if not req.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文本内容为空")

    # 先解析引擎与实际生效方案(生成器内不能 await; 失败由全局异常处理器统一返回)
    iterator, effective = await voice_service.tts_stream(
        req.text, req.engine, req.speaker, req.speed, req.sample_rate
    )

    sample_rate_holder = {"sr": req.sample_rate}

    def agen():
        """同步生成器: 逐块产出 PCM(引擎已在上方解析)"""
        try:
            for chunk, sr, is_final in iterator:
                sample_rate_holder["sr"] = sr
                yield chunk
        except Exception as e:
            logger.error(f"TTS 流式合成失败: {e}")
            return

    return StreamingResponse(
        agen(),
        media_type="audio/pcm",
        headers={
            "X-Sample-Rate": str(sample_rate_holder["sr"]),
            "X-Engine": effective.value,
        },
    )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice", tags=["语音合成 TTS"])
