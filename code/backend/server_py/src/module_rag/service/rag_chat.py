"""
基于 LangGraph 的 RAG 聊天服务
- AsyncPostgresSaver 做上下文历史管理 (checkpointer)
- StateGraph: 意图分析 → 知识库检索 → LLM 对话
- 流式输出按事件类型分类: AGENT_THINKING / TOOL_CALL / LLM_THINKING / ANSWER / STATUS / ERROR
- 对话总结: 压缩历史 + 生成标题
"""

import asyncio
import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.schema import StreamEvent
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from module_ai.service.llm import LLMService
from module_ai.utils.llm.types import RoleType, ModelType
from module_ai.utils.llm.chat.trim import messages_trim_with_max_tokens
from module_rag.config.checkpointer import get_checkpointer
from module_rag.dao.rag_chat_prompt import (
    RAG_CHAT_SYSTEM_PROMPT,
    RAG_CHAT_SYSTEM_PROMPT_TEMPLATE,
    RAG_SUPPLEMENT_CONTEXT_TEMPLATE,
    INTENT_ANALYSIS_SYSTEM_PROMPT,
    SUMMARIZE_SYSTEM_PROMPT,
)
from module_rag.do.chat_message import ChatMessageCreate
from module_rag.do.conversation import ChatRequest, ConversationUpdate
from module_rag.do.rag_chat import (
    ConversationSummary,
    InteractionKind,
    InteractionOption,
    InteractionSpec,
    RagChatState,
    RagHelpInfo,
    StreamEventType,
    StreamOne,
    SummaryState,
    GraphNode,
)
from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.service.conversation_title import maybe_auto_title
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
        llm_service: LLMService | None = None,
        user_model_service: UserModelService | None = None,
        chat_message_service: ChatMessageService | None = None,
        project_document_chunk_service: ProjectDocumentChunkService | None = None,
        conversation_service: ConversationService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.llm_service = llm_service or LLMService()
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
        """构建聊天 graph:
        [intent_analysis] → (需澄清?) [clarify_interaction] → END
                          → (需检索?) [knowledge_search] → (无结果?) [knowledge_gap] → END
                          → [chat] → END
        交互节点为"伪中断": 本次 run 结束并落 pending_interaction,
        用户下一条消息携带 interaction_response 续跑(经 checkpointer 共享 state)
        """

        graph = StateGraph(RagChatState)
        graph.add_node(GraphNode.INTENT, self._intent_analysis_node)
        graph.add_node(GraphNode.SEARCH, self._knowledge_search_node)
        graph.add_node(GraphNode.CHAT, self._chat_node)
        graph.add_node(GraphNode.CLARIFY, self._clarify_interaction_node)
        graph.add_node(GraphNode.GAP, self._knowledge_gap_node)

        # 条件路由(起点): 知识缺口响应(supplement/answer_directly)跳过意图与检索直接对话;
        # 有知识库 → 意图分析; 否则直接对话
        graph.add_conditional_edges(START, self._route_start)
        # 条件路由: 意图分析判定需要澄清 → 澄清交互; 需要外部信息才检索, 否则直接对话
        graph.add_conditional_edges(GraphNode.INTENT, self._route_after_intent)
        # 条件路由: 检索正常但无结果 → 知识缺口交互(邀请用户补充缺失内容)
        graph.add_conditional_edges(GraphNode.SEARCH, self._route_after_search)
        graph.add_edge(GraphNode.CHAT, END)
        graph.add_edge(GraphNode.CLARIFY, END)
        graph.add_edge(GraphNode.GAP, END)
        return graph

    @staticmethod
    def _route_start(state: RagChatState) -> GraphNode:
        """起点路由: 知识缺口交互的补充/直接回答响应直接进对话节点, 其余按常规流程"""
        resp = state.get("interaction_response")
        if (
            isinstance(resp, dict)
            and resp.get("kind") == InteractionKind.KNOWLEDGE_GAP
            and resp.get("action") in ("supplement", "answer_directly")
        ):
            return GraphNode.CHAT
        return GraphNode.INTENT if state.get("project_ids") else GraphNode.CHAT

    @staticmethod
    def _route_after_intent(state: RagChatState) -> GraphNode:
        """意图分析后的路由: 信息不足→澄清交互; 需外部信息且有知识库→检索; 否则直接对话"""
        info: RagHelpInfo | None = state.get("rag_help_info")
        # 同一轮待澄清请求只问一次(防止响应后仍判定需澄清造成循环打断)
        pending = state.get("pending_interaction")
        already_asked = isinstance(pending, dict) and pending.get("kind") == InteractionKind.CLARIFY
        if (
            info
            and info.needs_clarification
            and info.clarify_question
            and not already_asked
        ):
            return GraphNode.CLARIFY
        need_search = bool(state.get("project_ids")) and bool(
            info and info.is_need_external_info
        )
        return GraphNode.SEARCH if need_search else GraphNode.CHAT

    @staticmethod
    def _route_after_search(state: RagChatState) -> GraphNode:
        """检索后路由: 检索正常但零命中 → 知识缺口交互(用户可补充缺失内容)"""
        if not state.get("search_error") and not (state.get("knowledge_context_list") or []):
            return GraphNode.GAP
        return GraphNode.CHAT

    async def _intent_analysis_node(self, state: RagChatState) -> dict:
        """意图分析: 提取检索关键词 & 判断是否需要外部知识"""
        user_id: str = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id, streaming=False)
        messages: list[AnyMessage] = state["messages"]

        last_content = messages[-1].content if messages else ""
        if llm is None:
            # 无可用模型: 跳过意图分析, 用原问题检索(chat 节点会给出明确报错)
            logger.warning(f"用户 {user_id} 无可用对话模型, 意图分析跳过")
            rag_help_info = RagHelpInfo(
                intent=last_content,
                vector_search=last_content,
                full_text_search=last_content,
            )
        else:
            try:
                structured_llm = llm.with_structured_output(RagHelpInfo)
                rag_help_info: RagHelpInfo = await structured_llm.ainvoke(
                    [SystemMessage(content=INTENT_ANALYSIS_SYSTEM_PROMPT)] + messages
                )
            except Exception as e:
                logger.warning(f"意图分析失败，回退原问题: {e}")
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
            # 检索失败(模型网络错误/无 embedding 模型等)与"确实无相关片段"语义不同,
            # 错误原因写入 state, 由 SEARCH 节点结束事件透传到前端过程区块
            logger.warning(f"知识库检索失败: {e}")
            knowledge_context_list = []
            return {"knowledge_context_list": knowledge_context_list, "search_error": str(e)}

        return {"knowledge_context_list": knowledge_context_list, "search_error": None}

    async def _clarify_interaction_node(self, state: RagChatState) -> dict:
        """澄清交互节点: 问题信息不足, 结束本次 run 请求用户补充(伪中断)

        下一条消息携带 interaction_response(kind=clarify) 后重新走意图分析并检索
        """
        info: RagHelpInfo | None = state.get("rag_help_info")
        question = (
            info.clarify_question
            if info and info.clarify_question
            else "为了更准确地回答您的问题，能否补充一些关键信息？"
        )
        spec = InteractionSpec(
            kind=InteractionKind.CLARIFY,
            title="需要补充信息",
            question=question,
            options=[],
            allow_text=True,
            text_placeholder="请输入补充信息（如具体的项目/实体/时间范围等）",
            context={"intent": info.intent if info else ""},
        )
        return {"pending_interaction": spec.model_dump(), "interaction_response": None}

    async def _knowledge_gap_node(self, state: RagChatState) -> dict:
        """知识缺口交互节点: 检索零命中, 邀请用户补充缺失内容或选择继续方式(伪中断)"""
        info: RagHelpInfo | None = state.get("rag_help_info")
        spec = InteractionSpec(
            kind=InteractionKind.KNOWLEDGE_GAP,
            title="知识库中未找到相关内容",
            question="知识库中未检索到与该问题匹配的内容，您希望如何继续？",
            options=[
                InteractionOption(
                    label="补充相关内容",
                    value="supplement",
                    description="粘贴您掌握的相关资料，回答将结合补充内容生成",
                ),
                InteractionOption(
                    label="直接用 AI 知识回答",
                    value="answer_directly",
                    description="跳过知识库，使用模型自身知识回答",
                ),
                InteractionOption(
                    label="换个问法重新检索",
                    value="rephrase",
                    description="调整问题表述后重新检索知识库",
                ),
            ],
            allow_text=True,
            text_placeholder="选择「补充相关内容」或「换个问法」后，在此输入资料/新问题",
            context={
                "query": info.vector_search if info else "",
                "project_ids": state.get("project_ids", []),
            },
        )
        return {"pending_interaction": spec.model_dump(), "interaction_response": None}

    async def _chat_node(self, state: RagChatState) -> dict:
        """LLM 对话节点: 拼接 system prompt + 历史消息 → 生成回复"""
        user_id: str = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id)
        if llm is None:
            # 与 agent_chat 一致: 明确报错而非 AttributeError, 由 chat_stream 转 ERROR 事件
            raise ValueError("无可用对话模型, 请先在模型设置中绑定或由管理员配置默认公共模型")

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
        # 用户补充的缺失内容(knowledge_gap 交互)作为额外参考注入
        supplement_content: str | None = state.get("supplement_content")
        if supplement_content:
            system_prompt += RAG_SUPPLEMENT_CONTEXT_TEMPLATE.format(
                supplement_content=supplement_content
            )

        full_response = await llm.ainvoke(
            [SystemMessage(content=system_prompt)] + messages
        )
        return {
            "messages": [full_response],
            # 清理交互状态: 本轮流交互闭环, 防止残留影响后续问题
            "pending_interaction": None,
            "interaction_response": None,
            "supplement_content": None,
        }

    # ──────────────────────────────────────────────
    # 交互响应处理
    # ──────────────────────────────────────────────

    async def _validate_interaction_response(
        self, config: RunnableConfig, interaction_response: dict | None
    ) -> dict | None:
        """校验交互响应与 checkpointer 中待响应请求匹配(防过期/伪造), 返回归一化响应"""
        if not isinstance(interaction_response, dict) or not interaction_response.get("interaction_id"):
            return None
        pending: dict | None = None
        try:
            snapshot = await self.chat_compiled_graph.aget_state(config)
            values = getattr(snapshot, "values", None)
            pending = values.get("pending_interaction") if isinstance(values, dict) else None
        except Exception as e:
            logger.warning(f"读取待响应交互状态失败: {e}")
        if not isinstance(pending, dict) or pending.get("interaction_id") != interaction_response.get("interaction_id"):
            logger.info(
                f"忽略过期/不匹配的交互响应: {interaction_response.get('interaction_id')}"
            )
            return None
        return {
            "interaction_id": pending.get("interaction_id"),
            "kind": str(pending.get("kind") or ""),
            "action": str(interaction_response.get("action") or "submit"),
            "value": str(interaction_response.get("value") or ""),
        }

    @staticmethod
    def _interaction_store_message(
        message: str, normalized_response: dict | None
    ) -> str:
        """交互响应用户消息的可读兜底(空输入时生成自然语言, 避免历史出现协议噪音)"""
        if message:
            return message
        if not normalized_response:
            return message
        kind = normalized_response.get("kind")
        action = normalized_response.get("action")
        value = normalized_response.get("value", "")
        if kind == InteractionKind.CLARIFY:
            if action == "skip":
                return "（跳过补充，请基于现有信息回答）"
            return value or "（补充信息）"
        if kind == InteractionKind.KNOWLEDGE_GAP:
            if action == "supplement":
                return value or "（补充内容）"
            if action == "answer_directly":
                return "（无需知识库，请直接用你的知识回答我的上一个问题）"
            if action == "rephrase":
                return value or "请基于知识库重新检索并回答我之前的问题"
        return value or f"（{kind} 响应: {action}）"

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
        - TOOL_CALL:       知识库检索结果(含结构化 data)
        - LLM_THINKING:    LLM reasoning tokens (若模型支持)
        - ANSWER:          正式回答 token
        - INTERACTION:     用户交互请求(澄清/知识缺口补充)
        - ERROR:           异常
        """
        raw_message = (chat_request.message or "").strip()
        interaction_response: dict | None = getattr(chat_request, "interaction_response", None)

        if not raw_message and not interaction_response:
            yield StreamOne(
                content="消息内容不能为空",
                stream_event_type=StreamEventType.ERROR,
            )
            return

        # 1. 校验交互响应(与待响应请求匹配才生效, 否则按普通消息处理)
        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
        normalized_response = await self._validate_interaction_response(
            config, interaction_response
        )

        # 2. 持久化用户消息(交互响应空输入时用可读兜底文案)
        store_message = self._interaction_store_message(raw_message, normalized_response)
        chat_message_user = ChatMessageCreate(
            conversation_id=conversation_id,
            role=RoleType.USER,
            content=store_message,
        )
        await self.chat_message_service.add(chat_message_user)

        input_state: RagChatState = {
            "messages": [HumanMessage(content=store_message)],
            "project_ids": chat_request.project_ids or [],
            "user_id": user_id,
            "deep_thinking": chat_request.deep_thinking,
            "rerank_limit": getattr(chat_request, 'rerank_limit', 20), # 传递精排数量
            "interaction_response": normalized_response,
            "supplement_content": (
                normalized_response.get("value")
                if normalized_response
                and normalized_response.get("kind") == InteractionKind.KNOWLEDGE_GAP
                and normalized_response.get("action") == "supplement"
                else None
            ),
        }

        full_response = ""
        process_blocks: list[dict] = []
        try:
            # 兜底链可感知(v4 4.3): 绑定失效回退公共模型时, 先推送 STATUS 提示数据流向变化
            resolved = await self.user_model_service.resolve_model(
                user_id, ModelType.CHAT
            )
            if resolved.fallback_used and not resolved.binding_unset:
                # 绑定失效(被删/停用/无权)才提示数据流向变化; 未设置模型走默认公共模型属正常行为, 静默
                yield StreamOne(
                    content="绑定的对话模型不可用，已回退系统公共模型（数据将由公共模型处理，可在设置中调整）",
                    stream_event_type=StreamEventType.STATUS,
                )
            elif resolved.model_id is None:
                # 无可用模型(绑定失效/未绑定, 且无默认公共模型可回退): 直接报错, 不静默换模型
                yield StreamOne(
                    content="没有可用的对话模型(绑定失效且无默认公共模型可回退), 请在设置中绑定模型或联系管理员配置默认模型",
                    stream_event_type=StreamEventType.ERROR,
                )
                return
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
        finally:
            # 持久化助手消息(含过程区块，便于重新打开时恢复思考链路显示)
            # 客户端中止(停止生成)时生成器被 GeneratorExit 关闭, except Exception 捕获不到,
            # 必须放 finally 才能保证已生成的部分回答落库
            # 交互-only run(澄清/知识缺口, 无正文回答)也需落库: blocks 中含交互卡片供历史恢复
            if full_response or process_blocks:
                # 落库协程用 shield 脱离外层取消: 客户端断开时 sse-starlette 会取消流式任务,
                # finally 里直接 await 会被再次注入的 CancelledError 打断导致部分回答丢失
                persist_task = asyncio.create_task(
                    self.chat_message_service.add(
                        ChatMessageCreate(
                            conversation_id=conversation_id,
                            role=RoleType.ASSISTANT,
                            content=full_response,
                            blocks=process_blocks or None,
                        )
                    )
                )
                cancelled = False
                try:
                    await asyncio.shield(persist_task)
                except asyncio.CancelledError:
                    # 本任务被取消(客户端断开): 等落库协程完成后再传播取消
                    cancelled = True
                    try:
                        await persist_task
                    except Exception as e:
                        logger.error(f"助手消息持久化失败: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"助手消息持久化失败: {e}", exc_info=True)
                # 首次问答结束后自动生成会话标题(后台任务, 失败静默; 客户端中止也执行)
                # 交互响应的原文可能是空字符串(卡片点击提交), 用可读兜底文案生成标题
                if full_response:
                    asyncio.create_task(
                        maybe_auto_title(conversation_id, user_id, store_message, full_response)
                    )
                if cancelled:
                    raise

    @staticmethod
    def _accumulate_process_block(blocks: list[dict], item: StreamOne) -> None:
        """按 stream_event_type 累积过程区块(供前端折叠区恢复显示)

        data(结构化检索结果/交互请求等)随首条事件写入, 同类型合并时补写缺失键
        """
        evt = item.stream_event_type.value
        for b in blocks:
            if b.get("stream_event_type") == evt:
                b["content"] += item.content
                if item.data is not None and "data" not in b:
                    b["data"] = item.data
                return
        blocks.append(
            {
                "node_name": item.node_name,
                "stream_event_type": evt,
                "content": item.content,
                **({"data": item.data} if item.data is not None else {}),
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
        if llm is None:
            logger.warning(f"用户 {user_id} 无可用对话模型, 总结降级返回默认摘要")
            return {"summary": ConversationSummary()}
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
            # 仅在生成出有效标题时更新, 避免 LLM 失败/空标题覆盖原对话标题
            if summary.title:
                await self.conversation_service.update(
                    conversation_id, ConversationUpdate(title=summary.title)
                )
            return summary
        except Exception as e:
            logger.error(f"总结对话失败: {e}", exc_info=True)
            return ConversationSummary()
