"""语音 ASR/TTS 控制器

接口：
- POST /voice/asr            语音识别(音频上传)
- WS   /voice/asr/stream     语音识别(麦克风实时流式)
- POST /voice/tts/file       语音合成(返回完整音频文件 wav)
- POST /voice/tts/stream     语音合成(流式返回 PCM)

engine 参数可选：缺省时按模型配置(model_config 表 model_type=asr/tts)
自动选择方案；也可显式指定 sherpa / qwen 覆盖。
"""
import asyncio
import logging
import time

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import Response, StreamingResponse

from module_ai.config.server import module_app
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import ASRResponse, ASRStreamMessage, TTSRequest, VoiceEngine
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio_utils import pcm_to_wav_bytes

logger = logging.getLogger(__name__)

router = APIRouter()

# 流式 ASR 期望的 PCM 格式：16kHz 16bit 单声道
ASR_STREAM_SAMPLE_RATE = 16000


async def _resolve_engine(raw: str | None) -> VoiceEngine | None:
    """解析 engine 参数(空/None 时返回 None 由模型配置自动选择)"""
    if not raw:
        return None
    try:
        return VoiceEngine(raw)
    except ValueError:
        return VoiceEngine.SHERPA


@router.post(
    "/asr",
    response_model=ASRResponse,
    status_code=status.HTTP_200_OK,
    summary="语音识别(音频上传)",
)
async def asr_upload(
    audio: UploadFile,
    engine: VoiceEngine | None = Form(None),
    voice_service: VoiceService = Depends(get_voice_service),
):
    """上传音频文件进行语音识别

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    - **engine**: 引擎 sherpa / qwen(缺省按模型配置自动选择)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    start = time.time()
    try:
        text = await voice_service.asr(audio_bytes, engine)
        return ASRResponse(
            text=text, engine=engine or VoiceEngine.SHERPA, elapsed=round(time.time() - start, 3)
        )
    except Exception as e:
        logger.error(f"ASR 识别失败: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.websocket("/asr/stream")
async def asr_stream(ws: WebSocket):
    """麦克风实时流式语音识别

    协议：
    - 连接时通过 query 参数 engine 指定引擎(缺省按模型配置自动选择)
    - 客户端发送二进制帧：16kHz 16bit 单声道 PCM
    - 客户端发送文本 "EOS" 表示结束
    - 服务端返回 JSON: ASRStreamMessage(text, is_final, engine)
    """
    engine = await _resolve_engine(ws.query_params.get("engine"))

    await ws.accept()
    asr = await voice_service_get(ws, engine)
    if asr is None:
        return
    stream = None
    try:
        stream = asr.create_stream()
    except Exception as e:
        await ws.send_text(
            ASRStreamMessage(text=f"引擎初始化失败: {e}", is_final=True, engine=engine or VoiceEngine.SHERPA).model_dump_json()
        )
        await ws.close()
        return

    last_text = ""
    try:
        while True:
            msg = await ws.receive()
            if msg.get("text") is not None:
                if msg["text"].strip().upper() == "EOS":
                    final_text = asr.stream_result(stream, is_final=True)
                    if not final_text:
                        final_text = last_text
                    await ws.send_text(
                        ASRStreamMessage(
                            text=final_text, is_final=True, engine=engine or VoiceEngine.SHERPA
                        ).model_dump_json()
                    )
                    break
                continue
            data = msg.get("bytes")
            if data:
                try:
                    cur = asr.stream_accept(stream, data, ASR_STREAM_SAMPLE_RATE)
                    text = asr.stream_result(stream, is_final=False) or cur
                    if text and text != last_text:
                        last_text = text
                        await ws.send_text(
                            ASRStreamMessage(
                                text=text, is_final=False, engine=engine or VoiceEngine.SHERPA
                            ).model_dump_json()
                        )
                except Exception as e:
                    logger.warning(f"流式 ASR 帧处理失败: {e}")
    except WebSocketDisconnect:
        logger.info("ASR 流式客户端断开")
    except Exception as e:
        logger.error(f"ASR 流式异常: {e}")
    finally:
        if stream is not None:
            try:
                asr.stream_destroy(stream)
            except Exception:
                pass
        try:
            await ws.close()
        except Exception:
            pass


async def voice_service_get(ws: WebSocket, engine: VoiceEngine | None):
    """WebSocket 内获取语音服务与 ASR 引擎(失败时回报错误并关闭)"""
    from module_ai.dependencies.voice import get_voice_service

    service = get_voice_service()
    try:
        return await service.get_asr(engine)
    except Exception as e:
        logger.error(f"ASR 引擎获取失败: {e}")
        await ws.send_text(
            ASRStreamMessage(text=f"引擎初始化失败: {e}", is_final=True, engine=engine or VoiceEngine.SHERPA).model_dump_json()
        )
        await ws.close()
        return None


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
    try:
        pcm, sr = await voice_service.tts(
            req.text,
            req.engine,
            req.speaker,
            req.speed,
            req.sample_rate,
        )
    except Exception as e:
        logger.error(f"TTS 合成失败: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))

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

    # 先解析引擎与实际生效方案(生成器内不能 await)
    try:
        iterator, effective = await voice_service.tts_stream(
            req.text, req.engine, req.speaker, req.speed, req.sample_rate
        )
    except Exception as e:
        logger.error(f"TTS 引擎获取失败: {e}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))

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


module_app.include_router(router, prefix="/voice", tags=["语音 ASR/TTS"])
