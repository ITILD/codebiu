"""语音控制器(ASR/TTS/VAD/Denoise)

接口(路由前缀 /voice):
    - POST /asr         语音识别(音频上传, 可选 denoise/vad 前置处理管线)
          WS   /asr/stream  语音识别(麦克风实时流式, 可选服务端 VAD 静音过滤)
    - POST /tts/file    语音合成(返回完整音频文件 wav)
          POST /tts/stream  语音合成(流式返回 PCM)
    - POST /vad         语音活动检测(切分语音段)
    - POST /denoise     语音降噪(返回降噪后 wav)

engine 参数可选：缺省时按模型配置(model_config 表 model_type=asr/tts/vad/denoise)
自动选择方案；也可显式指定 sherpa / qwen 覆盖(vad/denoise 仅 sherpa)。
具体业务逻辑见 module_ai/service/voice.py(VoiceService)。
"""
import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse

from module_ai.config.server import module_app
from module_ai.dependencies.voice import get_voice_service
from module_ai.do.voice import (
    ASRResponse,
    ASRStreamMessage,
    TTSRequest,
    VADResponse,
    VoiceEngine,
    resolve_engine,
)
from module_ai.service.voice import VoiceService
from module_ai.utils.voice.audio import pcm_to_wav_bytes
from module_authorization.dependencies.auth import get_current_user_id_optional

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- 参数解析辅助(仅与请求格式相关) ----------

# 支持的 ASR 前置处理步骤
_PREPROCESS_STEPS = ("denoise", "vad")


def _parse_preprocess(raw: str | None) -> list[str]:
    """解析 preprocess 参数(逗号分隔, 仅保留合法步骤)"""
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip() in _PREPROCESS_STEPS]


async def _ws_user_id(token: str | None) -> str | None:
    """WS 连接 query 参数 token -> 用户ID(可选登录; 缺失/无效按匿名处理走全局配置)"""
    if not token:
        return None
    try:
        # 延迟导入避免模块加载期耦合
        from module_authorization.dao.token import TokenDao
        from module_authorization.dao.user import UserDao
        from module_authorization.service.auth import AuthService
        from module_authorization.service.token import TokenService
        from module_authorization.service.user import UserService

        auth = AuthService(UserService(UserDao()), TokenService(TokenDao()))
        return await auth.get_current_user_id(token)
    except Exception as e:
        logger.warning(f"WS 连接令牌解析失败, 按匿名处理: {e}")
        return None


# ---------- 语音识别(ASR) ----------


@router.post(
    "/asr",
    response_model=ASRResponse,
    status_code=status.HTTP_200_OK,
    summary="语音识别(音频上传, 可选前置处理)",
    tags=["语音识别 ASR"],
)
async def asr_upload(
    audio: UploadFile,
    engine: str | None = Form(None, description="引擎方案 online/local(兼容旧值 dashscope/sherpa/qwen), 缺省按模型配置自动选择"),
    preprocess: str = Form("", description="前置处理步骤(逗号组合): denoise(降噪)/vad(切段逐段识别), 如 'denoise,vad'"),
    voice_service: VoiceService = Depends(get_voice_service),
    current_user_id: str | None = Depends(get_current_user_id_optional),
):
    """上传音频文件进行语音识别

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    - **engine**: 引擎方案 online/local(缺省按用户绑定/模型配置自动选择)
    - **preprocess**: 前置处理管线(denoise→vad→逐段识别→合并), 与 engine 无关(VAD/降噪仅本地方案)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    steps = _parse_preprocess(preprocess)
    resolved = resolve_engine(engine)
    start = time.time()
    if steps:
        text = await voice_service.asr_preprocess(
            audio_bytes, steps, resolved, user_id=current_user_id
        )
    else:
        text = await voice_service.asr(audio_bytes, resolved, user_id=current_user_id)
    return ASRResponse(
        text=text,
        engine=await voice_service.effective_engine("asr", resolved, current_user_id),
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
    user_id = await _ws_user_id(ws.query_params.get("token"))

    await ws.accept()
    service = get_voice_service()
    # 先解析实际生效方案, 用于回显给客户端(缺省时为模型配置自身的方案)
    effective = await service.effective_engine("asr", engine, user_id)
    try:
        session = await service.create_asr_stream(engine, user_id, use_vad=use_vad)
    except Exception as e:
        logger.error(f"ASR 流式会话创建失败: {e}")
        await _send_and_close(ws, f"引擎初始化失败: {e}", effective)
        return
    if session.vad_error:
        await ws.send_text(
            ASRStreamMessage(
                text=f"VAD 不可用, 已按无 VAD 模式继续: {session.vad_error}",
                is_final=False,
                engine=effective,
            ).model_dump_json()
        )

    last_text = ""
    try:
        while True:
            msg = await ws.receive()
            if msg.get("text") is not None:
                if msg["text"].strip().upper() == "EOS":
                    final_text = await session.finish()
                    if not final_text:
                        final_text = last_text
                    await ws.send_text(
                        ASRStreamMessage(
                            text=final_text, is_final=True, engine=effective
                        ).model_dump_json()
                    )
                    break
                continue
            data = msg.get("bytes")
            if data:
                try:
                    await session.accept(data)
                    text = await session.result()
                    if text and text != last_text:
                        last_text = text
                        await ws.send_text(
                            ASRStreamMessage(
                                text=text, is_final=False, engine=effective
                            ).model_dump_json()
                        )
                except Exception as e:
                    logger.warning(f"流式 ASR 帧处理失败: {e}")
    except WebSocketDisconnect:
        logger.info("ASR 流式客户端断开")
    except Exception as e:
        logger.error(f"ASR 流式异常: {e}")
    finally:
        await session.close()
        try:
            await ws.close()
        except Exception:
            pass


async def _send_and_close(ws: WebSocket, text: str, engine) -> None:
    """发送错误消息并关闭连接(流式会话创建失败时)"""
    try:
        await ws.send_text(
            ASRStreamMessage(text=text, is_final=True, engine=engine or VoiceEngine.LOCAL).model_dump_json()
        )
        await ws.close()
    except Exception:
        pass


# ---------- 语音合成(TTS) ----------


@router.post(
    "/tts/file",
    summary="语音合成(返回完整音频文件)",
    tags=["语音合成 TTS"],
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
    tags=["语音合成 TTS"],
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


# ---------- 语音活动检测(VAD) ----------


@router.post(
    "/vad",
    response_model=VADResponse,
    summary="语音活动检测(切分语音段)",
    tags=["语音活动检测 VAD"],
)
async def vad_detect(
    audio: UploadFile,
    engine: str | None = Form(None, description="VAD 引擎方案 local(兼容旧值 sherpa/qwen), 缺省时按用户绑定/模型配置自动选择"),
    voice_service: VoiceService = Depends(get_voice_service),
    current_user_id: str | None = Depends(get_current_user_id_optional),
):
    """上传音频检测其中的语音段，返回各段的起止时间

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    start = time.time()
    segments = await voice_service.vad_segments(
        audio_bytes, resolve_engine(engine), user_id=current_user_id
    )
    return VADResponse(segments=segments, elapsed=round(time.time() - start, 3))


# ---------- 语音降噪(Denoise) ----------


@router.post(
    "/denoise",
    summary="语音降噪(返回降噪后音频)",
    tags=["语音降噪 Denoise"],
)
async def denoise_audio(
    audio: UploadFile,
    engine: str | None = Form(None, description="降噪引擎方案 local(兼容旧值 sherpa/qwen), 缺省时按用户绑定/模型配置自动选择"),
    voice_service: VoiceService = Depends(get_voice_service),
    current_user_id: str | None = Depends(get_current_user_id_optional),
):
    """上传含噪音频执行降噪，返回降噪后的 WAV 音频

    - **audio**: 音频文件(WAV/MP3 等可被解码格式)
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "音频文件为空")
    pcm, sr = await voice_service.denoise(
        audio_bytes, resolve_engine(engine), user_id=current_user_id
    )
    wav_bytes = pcm_to_wav_bytes(pcm, sr)
    return Response(
        content=wav_bytes,
        media_type="audio/wav",
        headers={"X-Sample-Rate": str(sr)},
    )


# 将路由注册到模块应用
module_app.include_router(router, prefix="/voice")
