"""语音合成(TTS)控制器

接口：
- POST /voice/tts/file    语音合成(返回完整音频文件 wav)
- POST /voice/tts/stream  语音合成(流式返回 PCM, online 方案走 CosyVoice 流式 WS 真流式)

engine 参数可选：online(远程API或本地vllm发布) / local(本机onnx或qwen推理),
兼容旧值 dashscope->online、sherpa/qwen->local 自动归一化; 缺省时按模型配置(model_config 表 model_type=tts)自动选择。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from module_ai.config.server import module_app
from module_ai.controller.voice.common import resolve_engine
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import TTSRequest
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio import pcm_to_wav_bytes
from module_authorization.dependencies.auth import get_current_user_id_optional

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/tts/file",
    summary="语音合成(返回完整音频文件)",
)
async def tts_file(
    req: TTSRequest,
    voice_service: VoiceService = Depends(get_voice_service),
    current_user_id: str | None = Depends(get_current_user_id_optional),
):
    """文本合成语音，返回完整 WAV 音频文件

    - **text**: 待合成文本
    - **engine**: 引擎方案 online/local(兼容旧值 dashscope/sherpa/qwen, 缺省按用户绑定/模型配置自动选择)
    """
    if not req.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文本内容为空")
    pcm, sr = await voice_service.tts(
        req.text,
        resolve_engine(req.engine),
        req.speaker,
        req.speed,
        req.sample_rate,
        user_id=current_user_id,
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
    current_user_id: str | None = Depends(get_current_user_id_optional),
):
    """文本合成语音，流式返回裸 PCM(16bit 单声道)

    通过响应头 X-Sample-Rate 返回采样率，客户端可边收边播。
    online 方案(dashscope 协议)走 CosyVoice 流式 WebSocket 真流式; 其余回退同步切片路径。
    - **text**: 待合成文本
    - **engine**: 引擎方案 online/local(兼容旧值 dashscope/sherpa/qwen, 缺省按用户绑定/模型配置自动选择)
    """
    if not req.text.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "文本内容为空")

    # 先解析引擎与实际生效方案(生成器内不能 await; 失败由全局异常处理器统一返回)
    iterator, effective, is_async = await voice_service.tts_stream_async(
        req.text, resolve_engine(req.engine), req.speaker, req.speed, req.sample_rate,
        user_id=current_user_id,
    )

    if is_async:
        async def agen_async():
            """异步生成器: 真流式逐块产出 PCM(引擎已在上方解析)"""
            try:
                async for chunk, sr, _is_final in iterator:
                    yield chunk
            except Exception as e:
                logger.error(f"TTS 流式合成失败: {e}")
                return

        return StreamingResponse(
            agen_async(),
            media_type="audio/pcm",
            headers={
                "X-Sample-Rate": str(req.sample_rate),
                "X-Engine": effective.value,
            },
        )

    def agen():
        """同步生成器: 逐块产出 PCM(引擎已在上方解析)"""
        try:
            for chunk, sr, is_final in iterator:
                yield chunk
        except Exception as e:
            logger.error(f"TTS 流式合成失败: {e}")
            return

    return StreamingResponse(
        agen(),
        media_type="audio/pcm",
        headers={
            "X-Sample-Rate": str(req.sample_rate),
            "X-Engine": effective.value,
        },
    )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice", tags=["语音合成 TTS"])
