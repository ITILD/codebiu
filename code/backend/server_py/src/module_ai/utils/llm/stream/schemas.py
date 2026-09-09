"""流式响应 schema

- StreamOne: 单条流式响应(通用)
- StreamChunkResponse: SSE 流式响应单 Chunk(LLM 对话/Agent 流式共用)
"""
from uuid import uuid4

from pydantic import BaseModel, Field

from module_ai.utils.llm.types import RoleType, StreamStatus


class StreamOne(BaseModel):
    content: str = Field(..., description="模型返回的内容")
    node_name: str = Field(..., description="节点名称")


class StreamChunkResponse(BaseModel):
    """流式响应主模型 单个Chunk"""

    status: StreamStatus = Field(StreamStatus.STREAM, description="响应状态")
    role: RoleType = Field(
        RoleType.ASSISTANT,
        description="消息角色:system、user、assistant 或具体业务模拟",
    )
    content: str | None = Field(None, description="响应内容")
    response_id: str = Field(
        default_factory=lambda: uuid4().hex, description="响应唯一标识 uuid"
    )
    timestamp: float = Field(0.0, description="Unix 时间戳（秒）")
    # 步骤节点名称
    node_name: str | None = Field(None, description="节点名称")
    # 流式事件分类(answer/llm_thinking/agent_thinking/tool_call/status/error)
    # 供前端区分"正式回答"与"思考/检索等过程区块"
    stream_event_type: str | None = Field(None, description="流式事件分类")
