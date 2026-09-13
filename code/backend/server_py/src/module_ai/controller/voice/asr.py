"""语音识别(ASR)控制器

接口：
- POST /voice/asr         语音识别(音频上传, 可选 denoise/vad 前置处理管线)
- WS   /voice/asr/stream  语音识别(麦克风实时流式, 可选服务端 VAD 静音过滤)

engine 参数可选：online(远程API或本地vllm发布) / local(本机onnx或qwen推理),
兼容旧值 dashscope->online、sherpa/qwen->local 自动归一化; 缺省时按模型配置(model_config 表 model_type=asr)自动选择。
"""
import logging
import time

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from module_ai.config.server import module_app
from module_ai.controller.voice.common import resolve_engine
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import ASRResponse, ASRStreamMessage, VoiceEngine, normalize_engine
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio import pcm16_to_float32

logger = logging.getLogger(__name__)

router = APIRouter()

# 流式 ASR 期望的 PCM 格式：16kHz 16bit 单声道
ASR_STREAM_SAMPLE_RATE = 16000

# 支持的前置处理步骤
_PREPROCESS_STEPS = ("denoise", "vad")


def _parse_preprocess(raw: str | None) -> list[str]:
    """解析 preprocess 参数(逗号分隔, 仅保留合法步骤)"""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip() in _PREPROCESS_STEPS]


@router.post(
    "/asr",
    response_model=ASRResponse,
    status_code=status.HTTP_200_OK,
    summary="语音识别(音频上传, 可选前置处理)",
)
async def asr_upload(
    audio: UploadFile,
    engine: str | None = Form(None, description="引擎方案 online/local(兼容旧值 dashscope/sherpa/qwen), 缺省按模型配置自动选择"),
    preprocess: str = Form("", description="前置处理步骤(逗号组合): denoise(降噪)/vad(切段逐段识别), 如 'denoise,vad'"),
    voice_service: VoiceService = Depends(get_voice_service),
):
    """上传音频文件进行语音识别

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    - **engine**: 引擎方案 online/local(缺省按模型配置自动选择)
    - **preprocess**: 前置处理管线(denoise→vad→逐段识别→合并), 与 engine 无关(VAD/降噪仅本地方案)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    steps = _parse_preprocess(preprocess)
    start = time.time()
    if steps:
        text = await voice_service.asr_preprocess(audio_bytes, steps, resolve_engine(engine))
    else:
        text = await voice_service.asr(audio_bytes, resolve_engine(engine))
    return ASRResponse(
        text=text,
        engine=normalize_engine(engine) or VoiceEngine.LOCAL,
        elapsed=round(time.time() - start, 3),
    )


@router.websocket("/asr/stream")
async def asr_stream(ws: WebSocket):
    """麦克风实时流式语音识别

    协议：
    - 连接时通过 query 参数 engine 指定方案(online/local, 旧值自动归一化), 缺省按模型配置自动选择
    - 连接时通过 query 参数 vad=true 启用服务端 VAD 静音过滤(仅语音段送识别, 省流量; 仅 local 方案可用)
    - 客户端发送二进制帧：16kHz 16bit 单声道 PCM
    - 客户端发送文本 "EOS" 表示结束
    - 服务端返回 JSON: ASRStreamMessage(text, is_final, engine)
    """
    engine = resolve_engine(ws.query_params.get("engine"))
    use_vad = str(ws.query_params.get("vad") or "").lower() in ("1", "true", "yes")

    await ws.accept()
    service = get_voice_service()
    try:
        asr = await service.get_asr(engine)
    except Exception as e:
        logger.error(f"ASR 引擎获取失败: {e}")
        await _send_and_close(ws, f"引擎初始化失败: {e}", engine)
        return

    # 可选服务端 VAD(静音过滤): 每连接一个实例
    vad = None
    if use_vad:
        try:
            vad = await service.get_vad()
        except Exception as e:
            logger.warning(f"VAD 引擎获取失败, 忽略 vad 参数: {e}")
            await ws.send_text(
                ASRStreamMessage(text=f"VAD 不可用, 已按无 VAD 模式继续: {e}", is_final=False, engine=engine or VoiceEngine.LOCAL).model_dump_json()
            )

    try:
        stream = await asr.create_stream_async()
    except Exception as e:
        logger.error(f"ASR 流式会话创建失败: {e}")
        await _send_and_close(ws, f"引擎初始化失败: {e}", engine)
        return

    last_text = ""
    try:
        while True:
            msg = await ws.receive()
            if msg.get("text") is not None:
                if msg["text"].strip().upper() == "EOS":
                    if vad is not None:
                        vad.flush()  # 弹出尾部未决语音段送识别
                        await _feed_vad_pending(asr, stream, vad)
                    final_text = await asr.stream_result_async(stream, is_final=True)
                    if not final_text:
                        final_text = last_text
                    await ws.send_text(
                        ASRStreamMessage(
                            text=final_text, is_final=True, engine=engine or VoiceEngine.LOCAL
                        ).model_dump_json()
                    )
                    break
                continue
            data = msg.get("bytes")
            if data:
                try:
                    if vad is not None:
                        await _accept_with_vad(asr, stream, vad, data)
                    else:
                        await asr.stream_accept_async(stream, data, ASR_STREAM_SAMPLE_RATE)
                    text = await asr.stream_result_async(stream, is_final=False)
                    if text and text != last_text:
                        last_text = text
                        await ws.send_text(
                            ASRStreamMessage(
                                text=text, is_final=False, engine=engine or VoiceEngine.LOCAL
                            ).model_dump_json()
                        )
                except Exception as e:
                    logger.warning(f"流式 ASR 帧处理失败: {e}")
    except WebSocketDisconnect:
        logger.info("ASR 流式客户端断开")
    except Exception as e:
        logger.error(f"ASR 流式异常: {e}")
    finally:
        try:
            await asr.stream_destroy_async(stream)
        except Exception:
            pass
        if vad is not None:
            try:
                vad.reset()
            except Exception:
                pass
        try:
            await ws.close()
        except Exception:
            pass


async def _accept_with_vad(asr, stream, vad, pcm_bytes: bytes) -> None:
    """服务端 VAD 过滤: 仅将语音段样本送入 ASR 流式会话"""
    samples = pcm16_to_float32(pcm_bytes)
    vad.accept_waveform(samples)
    while vad.is_speech_detected():
        segment = vad.pop_speech_segment()
        if segment is None:
            break
        seg, _start = segment
        await asr.stream_accept_async(stream, _seg_to_pcm16(seg), ASR_STREAM_SAMPLE_RATE)


async def _feed_vad_pending(asr, stream, vad) -> None:
    """EOS 前 flush 弹出尾部语音段送识别"""
    while vad.is_speech_detected():
        segment = vad.pop_speech_segment()
        if segment is None:
            break
        seg, _start = segment
        await asr.stream_accept_async(stream, _seg_to_pcm16(seg), ASR_STREAM_SAMPLE_RATE)


def _seg_to_pcm16(seg: np.ndarray) -> bytes:
    """float32 语音段 -> int16 PCM 字节(16k)"""
    return np.clip(seg, -1.0, 1.0).astype(np.int16).tobytes()


async def _send_and_close(ws: WebSocket, text: str, engine) -> None:
    """发送错误消息并关闭连接(流式会话创建失败时)"""
    try:
        await ws.send_text(
            ASRStreamMessage(text=text, is_final=True, engine=engine or VoiceEngine.LOCAL).model_dump_json()
        )
        await ws.close()
    except Exception:
        pass


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice", tags=["语音识别 ASR"])
