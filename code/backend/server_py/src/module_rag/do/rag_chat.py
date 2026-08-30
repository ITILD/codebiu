import logging
from typing import TypedDict
from enum import StrEnum
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from module_rag.do.project_document_chunk import ProjectDocumentChunkSearchResponse
logger = logging.getLogger(__name__)


class StreamEventType(StrEnum):
    """流式输出事件分类"""

    LLM_THINKING = "llm_thinking"  # LLM 推理/思考过程 (reasoning tokens)
    AGENT_THINKING = "agent_thinking"  # 策略思考过程 意图识别等
    # 思考结论的结论（人工或工具参与整理的信息）
    AGENT_THINKING_CONCLUSION = "agent_thinking_conclusion"
    TOOL_CALL = "tool_call"  # 工具调用（知识库检索等）
    FILE_GEN = "file_gen"  # 文件生成
    ANSWER = "answer"  # 正式回答
    STATUS = "status"  # 状态更新（进度提示）
    ERROR = "error"  # 错误信息


class ConversationSummary(BaseModel):
    """对话总结结构化输出模型

    用于 LLM 结构化输出，生成对话标题和摘要。
    """

    title: str = Field(
        default="",
        description="简短的对话标题(不超过20字，概括对话主题)",
    )
    summary: str = Field(
        default="",
        description="对话总结(不超过100字，概括对话关键信息)",
    )


class SummaryState(MessagesState):
    """对话总结 graph 状态"""

    user_id: str
    summary: ConversationSummary | None


class ConversationSummary(BaseModel):
    """对话摘要结构化模型"""

    title: str = Field(default="新对话", description="不超过20字的对话标题")
    summary: str = Field(default="", description="不超过100字的对话总结")


class RagHelpInfo(BaseModel):
    """RAG 帮助信息模型"""

    intent: str = Field(default="", description="用户意图")
    vector_search: str = Field(default="", description="对向量搜索有帮助的语句")
    full_text_search: str = Field(default="", description="用于全文检索语句")
    is_need_external_info: bool = Field(
        default=True, description="是否需要外部信息回答最新问题"
    )


class RagChatState(MessagesState):
    """RAG 聊天状态(扩展 MessagesState)"""

    project_ids: list[str]
    user_id: str
    rag_help_info: RagHelpInfo | None
    knowledge_context_list: list[ProjectDocumentChunkSearchResponse] | None
    deep_thinking: bool
    rerank_limit: int  # Rerank 精排返回的最大结果数


class StreamOne(BaseModel):
    content: str = Field(..., description="模型返回的内容")
    node_name: str = Field(..., description="节点名称")
    stream_event_type: StreamEventType = Field(
        StreamEventType.ANSWER, description="流式输出事件分类"
    )

# 业务
class GraphEvent(StrEnum):
    """LangGraph 原始事件名"""

    MODEL_STREAM = "on_chat_model_stream"
    NODE_START = "on_chain_start"
    NODE_END = "on_chain_end"


class GraphNode(StrEnum):
    """RAG 图节点名"""

    INTENT = "intent_analysis"
    SEARCH = "knowledge_search"
    CHAT = "chat"
    SUMMARY = "summarize"


# 节点名 → 业务流事件类型
NODE_EVENT_MAP: dict[GraphNode, StreamEventType] = {
    GraphNode.INTENT: StreamEventType.AGENT_THINKING,
    GraphNode.SEARCH: StreamEventType.TOOL_CALL,
    GraphNode.CHAT: StreamEventType.ANSWER,
}

# 节点名 → 前端状态提示
NODE_STATUS_MAP: dict[GraphNode, str] = {
    GraphNode.INTENT: "正在分析意图…",
    GraphNode.SEARCH: "正在检索知识库…",
    GraphNode.CHAT: "正在生成回答…",
}

# 知识库检索数量上限
SEARCH_LIMIT = 20