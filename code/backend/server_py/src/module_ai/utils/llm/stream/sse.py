from fastapi import Request
from module_ai.utils.llm.stream.agui import (
    AguiStreamTransformer,
    RunErrorEvent,
    encode_agui_event,
    normalize_llm_source,
)
from module_ai.utils.llm.stream.schemas import StreamChunkResponse
from module_ai.utils.llm.types import StreamStatus
from sse_starlette import EventSourceResponse, ServerSentEvent
import logging


logger = logging.getLogger(__name__)


async def event_generator(responses, request: Request = None):
    """SSE 流式响应生成器(旧协议: StreamChunkResponse)

    定位: 简单 AI 问答工具接口(/ai/llm/chat 默认协议)。
    RAG 会话等复杂 Agent 交互已统一走 AG-UI 协议(见 agui_event_generator),
    该旧协议仅保留给无需过程事件/交互卡片的轻量直连 LLM 场景。
    """
    try:
        # 发送开始信号
        start_response = StreamChunkResponse(status=StreamStatus.START)
        yield ServerSentEvent(data=start_response.model_dump_json())
        response_id = start_response.response_id

        # 流式处理响应内容
        async for chunk in responses:
            if request and await request.is_disconnected():
                logger.info(f"response_id:{response_id} 的客户端已断开连接，停止流式响应")
                break
            if chunk.content:
                yield ServerSentEvent(
                    data=StreamChunkResponse(
                        response_id=response_id,
                        content=chunk.content,
                        node_name=getattr(chunk, 'node_name', None),
                        stream_event_type=getattr(chunk, 'stream_event_type', None),
                    ).model_dump_json()
                )

        # 发送结束信号
        yield ServerSentEvent(
            data=StreamChunkResponse(status=StreamStatus.END).model_dump_json()
        )
    except Exception as e:
        logger.error(f"事件生成器错误：{e}")
        yield ServerSentEvent(
            data=StreamChunkResponse(
                status=StreamStatus.ERROR, content=str(e)
            ).model_dump_json()
        )


async def agui_event_generator(
    responses,
    request: Request = None,
    thread_id: str | None = None,
    initial_state: dict | None = None,
    raw_llm_chunks: bool = False,
):
    """SSE 流式响应生成器(AG-UI 协议)

    事件模型/序列化由官方 SDK `ag-ui-protocol` 提供(见 stream/agui.py 模块注释);
    每条 data 为官方事件的 camelCase JSON(by_alias=True)。

    :param responses: 业务 StreamOne 流(或 raw_llm_chunks=True 时 LangChain chunk 流)
    :param thread_id: AG-UI threadId(RAG 会话即 conversation_id)
    :param initial_state: 随 RUN_STARTED 下发的状态快照(STATE_SNAPSHOT)
    :param raw_llm_chunks: 输入是否为直连 LLM 的原始 chunk(归一化后再转换)
    """
    transformer = AguiStreamTransformer(thread_id=thread_id, initial_state=initial_state)
    source = normalize_llm_source(responses) if raw_llm_chunks else responses
    try:
        async for payload in transformer.transform(source):
            if request and await request.is_disconnected():
                logger.info(f"AG-UI run:{transformer.run_id} 的客户端已断开连接，停止流式响应")
                break
            yield ServerSentEvent(data=payload)
    except Exception as e:
        logger.error(f"AG-UI 事件生成器错误：{e}")
        yield ServerSentEvent(data=encode_agui_event(RunErrorEvent(message=str(e))))
