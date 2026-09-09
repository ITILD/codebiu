"""
基于 LangGraph 的智能体聊天服务(参考 module_rag/service/rag_chat.py 的调模型方式)

- 单节点 StateGraph: system_prompt 由对话关联的 agent 记录动态注入,
  一个编译好的通用图即可服务所有(内置/自定义)智能体
- AsyncPostgresSaver checkpointer 复用 module_rag, thread_id=conversation_id 隔离会话
- 流式事件复用 module_rag 的 StreamEventClassifier/StreamOne, 与前端过程区块协议一致
- 对话/消息持久化复用 module_rag 的 conversation/chat_message 表(已预留 agent_id 字段)
"""

import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from module_ai.utils.llm.types import RoleType
from module_ai.utils.llm.chat.trim import messages_trim_with_max_tokens
from module_rag.config.checkpointer import get_checkpointer
from module_rag.do.chat_message import ChatMessageCreate
from module_rag.do.rag_chat import StreamEventType, StreamOne
from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.utils.llm.stream_classifier import StreamEventClassifier
from module_rag.service.user_model import UserModelService
from module_agent.config.agent_seed import DEFAULT_AGENT_SYSTEM_PROMPT
from module_agent.do.agent_chat import AgentChatRequest, AgentChatState
from module_agent.service.agent import AgentService

logger = logging.getLogger(__name__)

# 通用图节点名(与 StreamEventClassifier 的 ANSWER 映射对齐)
CHAT_NODE = "chat"


class AgentChatService:
    """智能体聊天服务 (基于 LangGraph, 动态 system_prompt)"""

    def __init__(
        self,
        agent_service: AgentService | None = None,
        user_model_service: UserModelService | None = None,
        chat_message_service: ChatMessageService | None = None,
        conversation_service: ConversationService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.agent_service = agent_service or AgentService()
        self.user_model_service = user_model_service or UserModelService()
        self.chat_message_service = chat_message_service or ChatMessageService()
        self.conversation_service = conversation_service or ConversationService()
        self.compiled_graph: CompiledStateGraph | None = None
        self._classifier = StreamEventClassifier()

    async def _init_compiled_graph(self) -> None:
        """编译通用聊天图(checkpointer 按 thread_id 隔离会话)"""
        checkpointer = await get_checkpointer()
        graph = StateGraph(AgentChatState)
        graph.add_node(CHAT_NODE, self._chat_node)
        graph.add_edge(START, CHAT_NODE)
        graph.add_edge(CHAT_NODE, END)
        self.compiled_graph = graph.compile(checkpointer=checkpointer)

    async def _chat_node(self, state: AgentChatState) -> dict:
        """智能体对话节点: agent system_prompt + 历史消息 → 生成回复"""
        user_id: str = state["user_id"]
        llm = await self.user_model_service.get_llm_by_user_id(user_id)
        if llm is None:
            raise ValueError("无可用对话模型, 请先在模型配置中绑定或由管理员配置公共模型")

        messages = messages_trim_with_max_tokens(list(state["messages"]))
        full_response = await llm.ainvoke(
            [SystemMessage(content=state["system_prompt"])] + messages
        )
        return {"messages": [full_response]}

    async def _resolve_system_prompt(self, conversation_id: str) -> str:
        """解析对话关联智能体的 system_prompt(未关联/智能体已删除时用默认提示词兜底)"""
        conv = await self.conversation_service.get(conversation_id)
        agent_id = getattr(conv, "agent_id", None) if conv else None
        if agent_id:
            agent = await self.agent_service.get(agent_id)
            if agent and agent.system_prompt:
                return agent.system_prompt
        return DEFAULT_AGENT_SYSTEM_PROMPT

    async def stream_chat(
        self,
        conversation_id: str,
        user_id: str,
        chat_request: AgentChatRequest,
    ) -> AsyncGenerator[StreamOne, None]:
        """
        智能体流式聊天生成器，按事件类型 yield StreamOne:
        - STATUS: 阶段提示
        - LLM_THINKING: 推理过程(若模型支持)
        - ANSWER: 正式回答 token
        - ERROR: 异常
        """
        system_prompt = await self._resolve_system_prompt(conversation_id)

        # 1. 持久化用户消息
        await self.chat_message_service.add(
            ChatMessageCreate(
                conversation_id=conversation_id,
                role=RoleType.USER,
                content=chat_request.message,
            )
        )

        config: RunnableConfig = {"configurable": {"thread_id": conversation_id}}
        input_state: AgentChatState = {
            "messages": [HumanMessage(content=chat_request.message)],
            "system_prompt": system_prompt,
            "user_id": user_id,
        }

        full_response = ""
        process_blocks: list[dict] = []
        try:
            async for event in self.compiled_graph.astream_events(
                input_state, config=config, version="v2"
            ):
                for item in self._classifier.classify(event):
                    if item.stream_event_type == StreamEventType.ANSWER:
                        full_response += item.content
                    elif item.stream_event_type != StreamEventType.STATUS:
                        # 收集思考等过程区块(跳过 status: 瞬态进度，由前端实时展示)
                        self._accumulate_process_block(process_blocks, item)

                    yield item

        except Exception as e:
            logger.error(f"智能体流式聊天失败: {e}", exc_info=True)
            yield StreamOne(
                content=f"服务异常: {e}",
                stream_event_type=StreamEventType.ERROR,
            )

        # 2. 持久化助手消息(含过程区块，便于重新打开时恢复思考链路显示)
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
