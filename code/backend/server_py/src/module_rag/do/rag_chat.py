import logging
from typing import TypedDict
from enum import StrEnum
from uuid import uuid4
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
    INTERACTION = "interaction"  # 用户交互请求(信息澄清/知识缺口补充等, AG-UI 模式经 CUSTOM rag.interaction 下发)


class ConversationSummary(BaseModel):
    """对话总结结构化输出模型(用于 LLM 结构化输出, 生成对话标题和摘要)"""

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


class RagHelpInfo(BaseModel):
    """RAG 帮助信息模型"""

    intent: str = Field(default="", description="用户意图")
    vector_search: str = Field(default="", description="对向量搜索有帮助的语句")
    full_text_search: str = Field(default="", description="用于全文检索语句")
    is_need_external_info: bool = Field(
        default=True, description="是否需要外部信息回答最新问题"
    )
    needs_clarification: bool = Field(
        default=False,
        description="最新问题信息不足(指代不明/缺少关键实体), 需要用户澄清后才能有效检索",
    )
    clarify_question: str = Field(
        default="",
        description="向用户提出的澄清问题(needs_clarification 时使用, 需具体明确)",
    )


# ──────────────────────────────────────────────
# 用户交互请求(缺失内容补充/信息澄清)
# ──────────────────────────────────────────────


class InteractionKind(StrEnum):
    """交互请求类型"""

    CLARIFY = "clarify"  # 问题信息不足, 请用户澄清
    KNOWLEDGE_GAP = "knowledge_gap"  # 知识库未检索到相关内容, 请用户补充/选择继续方式


class InteractionOption(BaseModel):
    """交互请求候选项"""

    label: str = Field(..., description="选项展示文案")
    value: str = Field(..., description="选项值(提交时作为 action/value 回传)")
    description: str = Field("", description="选项说明")


class InteractionSpec(BaseModel):
    """用户交互请求规格(AG-UI 模式经 CUSTOM rag.interaction 下发, 前端渲染交互卡片)"""

    interaction_id: str = Field(
        default_factory=lambda: uuid4().hex, description="交互请求唯一ID(响应时校验)"
    )
    kind: InteractionKind = Field(..., description="交互类型(clarify/knowledge_gap)")
    title: str = Field(..., description="卡片标题")
    question: str = Field(..., description="向用户提出的问题")
    options: list[InteractionOption] = Field(
        default_factory=list, description="候选项(空则纯文本输入)"
    )
    allow_text: bool = Field(True, description="是否允许自由文本输入")
    text_placeholder: str = Field("", description="文本输入占位提示")
    context: dict = Field(default_factory=dict, description="附加上下文(检索语句/结果数等)")


class RagChatState(MessagesState):
    """RAG 聊天状态(扩展 MessagesState)"""

    project_ids: list[str]
    user_id: str
    rag_help_info: RagHelpInfo | None
    knowledge_context_list: list[ProjectDocumentChunkSearchResponse] | None
    deep_thinking: bool
    rerank_limit: int  # Rerank 精排返回的最大结果数
    search_error: str | None  # 知识库检索失败原因(None=检索正常), 供过程区块区分"失败"与"无结果"
    # ── 用户交互(跨 run 持久于 checkpointer) ──
    pending_interaction: dict | None  # 待响应的交互请求(InteractionSpec 序列化)
    interaction_response: dict | None  # 本次请求携带的交互响应 {interaction_id, kind, action, value}
    supplement_content: str | None  # 用户补充的知识内容(knowledge_gap 响应), 注入 chat 上下文


class StreamOne(BaseModel):
    content: str = Field(..., description="模型返回的内容")
    # 默认空串: chat_stream 的回退提示/错误事件不携带节点名, 必填会抛 ValidationError 中断流
    node_name: str = Field("", description="节点名称")
    stream_event_type: StreamEventType = Field(
        StreamEventType.ANSWER, description="流式输出事件分类"
    )
    # 结构化载荷(检索结果/意图结论/交互请求), AG-UI 协议层消费, 旧协议前端忽略
    data: dict | None = Field(None, description="结构化事件载荷")

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
    CLARIFY = "clarify_interaction"  # 意图澄清交互(等待用户补充信息)
    GAP = "knowledge_gap"  # 知识缺口交互(检索无结果, 等待用户补充内容/选择继续方式)


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
    GraphNode.CLARIFY: "正在确认补充信息…",
    GraphNode.GAP: "正在评估知识覆盖…",
}

# 知识库检索数量上限
SEARCH_LIMIT = 20