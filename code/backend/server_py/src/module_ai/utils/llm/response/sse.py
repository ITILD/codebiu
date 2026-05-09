from fastapi import Request
from pydantic import BaseModel
from module_ai.do.llm_base import (
    StreamChunkResponse,
)
from module_ai.utils.llm.do.llm_type import StreamStatus
from sse_starlette import EventSourceResponse, ServerSentEvent
import logging


logger = logging.getLogger(__name__)


async def event_generator(responses, request: Request = None):
    """SSE 流式响应生成器"""
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
                        node_name=getattr(chunk, 'node_name', None)
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
