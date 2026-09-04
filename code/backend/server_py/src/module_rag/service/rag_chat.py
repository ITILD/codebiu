"""
基于 LangGraph 的 RAG 聊天服务
- AsyncPostgresSaver 做上下文历史管理 (checkpointer)
- StateGraph: 意图分析 → 知识库检索 → LLM 对话
- 流式输出按事件类型分类: AGENT_THINKING / TOOL_CALL / LLM_THINKING / ANSWER / STATUS / ERROR
- 对话总结: 压缩历史 + 生成标题
"""

import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.schema import StreamEvent
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from module_ai.service.llm_base import LLMBaseService
from module_ai.utils.llm.do.llm_type import RoleType
from module_ai.utils.llm.message.trim import messages_trim_with_max_tokens
from module_rag.config.checkpointer import get_checkpointer
from module_rag.dao.rag_chat_prompt import (
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_SYSTEM_PROMPT_TEMPLATE,
    INTENT_ANALYSIS_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
)
from module_rag.do.chat_message import ChatMessageCreate
from module_rag.do.conversation import ChatRequest, ConversationUpdate
from module_rag.do.rag_chat import (
    ConversationSummary,
    RagChatState,
    RagHelpInfo,
    StreamEventType,
    StreamOne,
    SummaryState,
    GraphNode,
)
from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.service.user_model import UserModelService
from module_rag.do.project_document_chunk import (
    ProjectDocumentChunkSearchResponse,
    SearchRequest,
)
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_rag.utils.llm.stream_classifier import StreamEventClassifier

logger = logging.getLogger(__name__)


class RagChatService:
    """RAG 聊天服务 (基于 LangGraph)"""

    def __init__(
        self,
        llm_base_service: LLMBaseService | None = None,
        user_model_service: UserModelService | None = None,
        chat_message_service: ChatMessageService | None = None,
        project_document_chunk_service: ProjectDocumentChunkService | None = None,
        conversation_service: ConversationService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.llm_base_service = llm_base_service or LLMBaseService()
        self.user_model_service = user_model_service or UserModelService()
        self.chat_message_service = chat_message_service or ChatMessageService()
        self.project_document_chunk_service = project_document_chunk_service or ProjectDocumentChunkService()
        self.conversation_service = conversation_service or ConversationService()
        self.chat_compiled_graph: CompiledStateGraph | None = None
        self.summary_compiled_graph: CompiledStateGraph | None = None
        self._classifier = StreamEventClassifier()

    # ──────────────────────────────────────────────
    # Graph 初始化
    # ──────────────────────────────────────────────

    async def _init_compiled_graphs(self) -> None:
        """编译 chat / summary 两个 graph，checkpointer 按 thread_id 隔离会话"""
        checkpointer = await get_checkpointer()
        self.chat_compiled_graph = self._build_chat_graph().compile(
            checkpointer=checkpointer
        )
        self.summary_compiled_graph = self._build_summary_graph().compile(
            checkpointer=checkpointer
        )

    # ──────────────────────────────────────────────
    # Chat Graph
    # ──────────────────────────────────────────────

    def _build_chat_graph(self) -> StateGraph:
        """构建聊天 graph: [intent_analysis] → [knowledge_search] → chat → END"""

        graph = StateGraph(RagChatState)
        graph.add_node(GraphNode.INTENT, self._intent_analysis_node)
        graph.add_node(GraphNode.SEARCH, self._knowledge_search_node)
        graph.add_node(GraphNode.CHAT, self._chat_node)

        # 条件路由: 有知识库 → 意图分析; 否则直接对话
        graph.add_conditional_edges(
            START,
            lambda state: (
                GraphNode.INTENT if state.get("project_ids") else GraphNode.CHAT
            ),
        )
        graph.add_edge(GraphNode.INTENT, GraphNode.SEARCH)
        graph.add_edge(GraphNode.SEARCH, GraphNode.CHAT)
        graph.add_edge(GraphNode.CHAT, END)
        return graph

    async def _intent_analysis_node(self, state: RagChatState) -> dict:
        """意图分析: 提取检索关键词 & 判断是否需要外部知识"""
        user_id: str = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id, streaming=False)
        messages: list[AnyMessage] = state["messages"]

        try:
            structured_llm = llm.with_structured_output(RagHelpInfo)
            rag_help_info: RagHelpInfo = await structured_llm.ainvoke(
                [SystemMessage(content=INTENT_ANALYSIS_SYSTEM_PROMPT)] + messages
            )
        except Exception as e:
            logger.warning(f"意图分析失败，回退原问题: {e}")
            last_content = messages[-1].content if messages else ""
            rag_help_info = RagHelpInfo(
                intent=last_content,
                vector_search=last_content,
                full_text_search=last_content,
            )
        return {"rag_help_info": rag_help_info}

    async def _knowledge_search_node(self, state: RagChatState) -> dict:
        """知识库混合检索 (向量 + 全文)"""
        rag_help_info: RagHelpInfo | None = state.get("rag_help_info")
        project_ids: list[str] = state.get("project_ids", [])
        user_id: str = state["user_id"]
        deep_thinking: bool = state.get("deep_thinking", True)
        # state 中获取前端传来的 rerank_limit，若无则给默认值 20
        rerank_limit: int = state.get("rerank_limit", 20)
        search_limit: int = state.get("search_limit", 50)
        # 不需要外部信息时跳过
        if not (project_ids and rag_help_info and rag_help_info.is_need_external_info):
            return {"knowledge_context_list": []}
        request = SearchRequest(
            query_content=rag_help_info.vector_search,
            query_text=rag_help_info.full_text_search,
            project_ids=project_ids,
            limit=search_limit,
            rerank_limit=rerank_limit,
            enable_rerank=deep_thinking,
        )
        # chunk 最大500 500*100 最大50k

        try:
            knowledge_context_list = await self.project_document_chunk_service.search(request, user_id)
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            knowledge_context_list = []

        return {"knowledge_context_list": knowledge_context_list}

    async def _chat_node(self, state: RagChatState) -> dict:
        """LLM 对话节点: 拼接 system prompt + 历史消息 → 生成回复"""
        user_id: str = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id)

        messages = messages_trim_with_max_tokens(list(state["messages"]))
        knowledge_context_list: list[ProjectDocumentChunkSearchResponse] = state.get(
            "knowledge_context_list", []
        )

        system_prompt = RAG_CHAT_SYSTEM_PROMPT
        if knowledge_context_list:
            knowledge_context = "\n".join(
                item.content
                for item in knowledge_context_list
                if getattr(item, "content", "")
            )
            system_prompt += RAG_CHAT_SYSTEM_PROMPT_TEMPLATE.format(
                knowledge_context=knowledge_context
            )

        full_response = await llm.ainvoke(
            [SystemMessage(content=system_prompt)] + messages
        )
        return {"messages": [full_response]}

    # ──────────────────────────────────────────────
    # 流式聊天入口
    # ──────────────────────────────────────────────

    async def chat_stream(
        self,
        conversation_id: str,
        user_id: str,
        chat_request: ChatRequest,
    ) -> AsyncGenerator[StreamOne, None]:
        """
        流式聊天生成器，按事件类型 yield StreamOne:
        - STATUS:          阶段提示 (意图分析中 / 检索中)
        - AGENT_THINKING:  意图分析结果
        - TOOL_CALL:       知识库检索结果
        - LLM_THINKING:    LLM reasoning tokens (若模型支持)
        - ANSWER:          正式回答 token
        - ERROR:           异常
        """
        # 1. 持久化用户消息
        chat_message_user = ChatMessageCreate(
            conversation_id=conversation_id,
            role=RoleType.USER,
            content=chat_request.message,
        )
        await self.chat_message_service.add(chat_message_user)

        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
        input_state: RagChatState = {
            "messages": [HumanMessage(content=chat_request.message)],
            "project_ids": chat_request.project_ids or [],
            "user_id": user_id,
            "deep_thinking": chat_request.deep_thinking,
            "rerank_limit": getattr(chat_request, 'rerank_limit', 20), # 传递精排数量
        }

        full_response = ""
        process_blocks: list[dict] = []
        try:
            async for event in self.chat_compiled_graph.astream_events(
                input_state, config=config, version="v2"
            ):
                for item in self._classifier.classify(event):
                    if item.stream_event_type == StreamEventType.ANSWER:
                        full_response += item.content
                    elif item.stream_event_type != StreamEventType.STATUS:
                        # 收集思考/检索等过程区块(跳过 status: 瞬态进度，由前端实时展示)
                        self._accumulate_process_block(process_blocks, item)

                    yield item

        except Exception as e:
            logger.error(f"流式聊天失败: {e}", exc_info=True)
            yield StreamOne(
                content=f"服务异常: {e}",
                stream_event_type=StreamEventType.ERROR,
            )

        # 5. 持久化助手消息(含过程区块，便于重新打开时恢复思考链路显示)
        if full_response:
            await self.chat_message_service.add(
                ChatMessageCreate(
                    conversation_id=conversation_id,
                    role=RoleType.ASSISTANT,
                    content=full_response,
                    blocks=process_blocks or None,
                )
            )

    @staticmethod
    def _accumulate_process_block(blocks: list[dict], item: StreamOne) -> None:
        """按 stream_event_type 累积过程区块(供前端折叠区恢复显示)"""
        evt = item.stream_event_type.value
        for b in blocks:
            if b.get("stream_event_type") == evt:
                b["content"] += item.content
                return
        blocks.append(
            {
                "node_name": item.node_name,
                "stream_event_type": evt,
                "content": item.content,
            }
        )

    # ──────────────────────────────────────────────
    # Summary Graph
    # ──────────────────────────────────────────────

    def _build_summary_graph(self) -> StateGraph:
        """构建对话总结 graph"""
        graph = StateGraph(SummaryState)
        graph.add_node(GraphNode.SUMMARY, self._summarize_node)
        graph.add_edge(START, GraphNode.SUMMARY)
        graph.add_edge(GraphNode.SUMMARY, END)
        return graph

    async def _summarize_node(self, state: SummaryState) -> dict:
        """LLM 结构化总结: 生成标题 + 摘要"""
        user_id = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id, streaming=False)
        structured_llm = llm.with_structured_output(ConversationSummary)

        messages: list[AnyMessage] = [
            SystemMessage(content=SUMMARIZE_SYSTEM_PROMPT)
        ] + list(state["messages"])

        try:
            result: ConversationSummary = await structured_llm.ainvoke(messages)
        except Exception as e:
            logger.warning(f"LLM 结构化总结失败: {e}")
            result = ConversationSummary()
        return {"summary": result}

    async def summarize_conversation(
        self, conversation_id: str, user_id: str
    ) -> ConversationSummary:
        """总结对话并持久化标题"""
        try:
            config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
            result = await self.summary_compiled_graph.ainvoke(
                SummaryState(user_id=user_id), config=config
            )
            summary: ConversationSummary = (
                result.get("summary") or ConversationSummary()
            )
            await self.conversation_service.update(
                conversation_id, ConversationUpdate(title=summary.title)
            )
            return summary
        except Exception as e:
            logger.error(f"总结对话失败: {e}", exc_info=True)
            return ConversationSummary()
