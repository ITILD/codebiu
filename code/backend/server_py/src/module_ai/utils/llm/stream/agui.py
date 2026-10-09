"""AG-UI 协议(Agent User Interaction Protocol)事件层 — 基于官方 SDK

官方实现: pip 包 ``ag-ui-protocol``(import 名 ``ag_ui``)。
事件模型定义在 ``ag_ui.core``: 由官方 1.0 规范 schema 生成,
字段用 snake_case 声明、序列化自动输出 camelCase 别名(by_alias=True),
且无值的可选字段自动省略(不写 JSON null)。
文档: https://docs.ag-ui.com/sdk/python/core/events

协议分层与本项目取舍:
- 事件模型/编码 → 官方 ``ag_ui.core``(本模块直接复用并 re-export, 不自实现)
- 业务事件映射 → 本模块 ``AguiStreamTransformer``: 把内部 StreamOne 流翻译为
  官方事件对象。官方 LangGraph 适配器 ``ag-ui-langgraph``(LangGraphAgent +
  add_langgraph_fastapi_endpoint) 面向"把整个 graph 托管为标准 RunAgentInput
  端点"; 本项目 RAG 图需自管鉴权/消息落库/伪中断交互, 不适合整体托管, 故只
  复用官方事件模型层。
- 传输 → SSE(sse-starlette), 每条 data 为 ``event.model_dump_json(by_alias=True)``

事件语义速查(规范 https://docs.ag-ui.com/concepts/events):
- RUN_STARTED / RUN_FINISHED / RUN_ERROR  一次运行的起止与失败(必发首尾)
- STEP_STARTED / STEP_FINISHED            运行内具名步骤(此处 = LangGraph 节点)
- TEXT_MESSAGE_START/CONTENT/END          助手正文流(CONTENT 增量 delta 拼接)
- TOOL_CALL_START/ARGS/END/RESULT         工具调用(ARGS 为入参增量;
                                           1.0 起 START 不含 input 字段;
                                           RESULT 结构化结果 JSON, 自带 messageId)
- STATE_SNAPSHOT                          全量状态快照(RUN_STARTED 后随发)
- REASONING_*                             推理过程流(已废弃的 THINKING_* 继任,
                                           按 message_id 分段)
- CUSTOM                                  协议扩展点, 业务自定义载荷(name 必填)

业务自定义 CUSTOM 事件名约定(命名空间.事件):
- rag.status         进度提示 { message, node }
- rag.intent_result  意图分析结构化结论
- rag.interaction    用户交互请求卡片(InteractionSpec, 澄清/知识缺口补充)
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

# ── 官方事件模型(1.0 规范生成, re-export 供 service/controller 层直接构造) ──
from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    ReasoningEndEvent,
    ReasoningMessageContentEvent,
    ReasoningMessageEndEvent,
    ReasoningMessageStartEvent,
    ReasoningStartEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

logger = logging.getLogger(__name__)

__all__ = [
    # 官方事件模型 re-export
    "BaseEvent",
    "CustomEvent",
    "EventType",
    "ReasoningEndEvent",
    "ReasoningMessageContentEvent",
    "ReasoningMessageEndEvent",
    "ReasoningMessageStartEvent",
    "ReasoningStartEvent",
    "RunErrorEvent",
    "RunFinishedEvent",
    "RunStartedEvent",
    "StateSnapshotEvent",
    "StepFinishedEvent",
    "StepStartedEvent",
    "TextMessageContentEvent",
    "TextMessageEndEvent",
    "TextMessageStartEvent",
    "ToolCallArgsEvent",
    "ToolCallEndEvent",
    "ToolCallResultEvent",
    "ToolCallStartEvent",
    # 本模块业务层
    "AguiStreamTransformer",
    "encode_agui_event",
    "normalize_llm_chunk",
    "normalize_llm_source",
    "CUSTOM_NAME_STATUS",
    "CUSTOM_NAME_INTENT_RESULT",
    "CUSTOM_NAME_INTERACTION",
]

# 业务 StreamEventType → AG-UI 的自定义事件名约定
CUSTOM_NAME_STATUS = "rag.status"
CUSTOM_NAME_INTENT_RESULT = "rag.intent_result"
CUSTOM_NAME_INTERACTION = "rag.interaction"


def encode_agui_event(event: BaseEvent) -> str:
    """官方事件 → SSE data 载荷(JSON 字符串)

    by_alias=True 输出协议规定的 camelCase 字段(threadId/messageId/toolCallId/
    stepName/...); 官方模型基类自动省略无值可选字段。前端类型与之逐字段对齐。
    """
    return event.model_dump_json(by_alias=True)


class AguiStreamTransformer:
    """业务 StreamOne 流 → 官方 AG-UI 事件流的有状态转换器

    状态机职责(输入为内部 StreamOne, 输出为官方事件对象):
    - 首条前发 RUN_STARTED(+可选 STATE_SNAPSHOT), 结束发 RUN_FINISHED / 出错发 RUN_ERROR
    - STATUS(节点切换) → STEP_STARTED/STEP_FINISHED + CUSTOM(rag.status 进度提示)
    - ANSWER → TEXT_MESSAGE_START/CONTENT/END(单条助手消息, 按 messageId 串联)
    - LLM_THINKING / AGENT_THINKING → REASONING_* 推理流(按节点分段, 段=reasoning
      message_id, 节点切换时先闭旧段再开新段)
    - AGENT_THINKING_CONCLUSION → CUSTOM(rag.intent_result, 结构化意图结论)
    - TOOL_CALL → TOOL_CALL_START/ARGS/END/RESULT(检索入参走 ARGS 增量,
      结构化 results 走 RESULT.content)
    - INTERACTION → CUSTOM(rag.interaction, 用户交互请求卡片)
    - ERROR → RUN_ERROR
    """

    def __init__(
        self,
        thread_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ):
        # threadId: AG-UI 会话线程(RAG 场景即 conversation_id); runId: 本次运行
        self.thread_id = thread_id or uuid4().hex
        self.run_id = uuid4().hex
        self._initial_state = initial_state
        # 运行状态标记(开闭分组的游标)
        self._message_id: str | None = None
        self._reasoning_id: str | None = None
        self._reasoning_key: tuple[str, str] | None = None
        self._current_step: str | None = None
        self._errored = False

    # ── 单事件便捷构造 ──────────────────────────

    def _started(self) -> RunStartedEvent:
        return RunStartedEvent(thread_id=self.thread_id, run_id=self.run_id)

    def _finished(self) -> RunFinishedEvent:
        return RunFinishedEvent(thread_id=self.thread_id, run_id=self.run_id)

    # ── 开闭分组 ────────────────────────────────

    def _open_step(self, events: list[BaseEvent], step_name: str) -> None:
        """切换具名步骤: 先闭旧步骤(STEP_FINISHED)再开新步骤(STEP_STARTED)"""
        if not step_name or step_name == self._current_step:
            return
        if self._current_step:
            events.append(StepFinishedEvent(step_name=self._current_step))
        self._current_step = step_name
        events.append(StepStartedEvent(step_name=step_name))

    def _open_message(self, events: list[BaseEvent]) -> str:
        """惰性开启正文消息(TEXT_MESSAGE_START), 全程单条消息"""
        if self._message_id is None:
            self._message_id = uuid4().hex
            events.append(TextMessageStartEvent(message_id=self._message_id, role="assistant"))
        return self._message_id

    def _open_reasoning(self, events: list[BaseEvent], node_name: str) -> str:
        """按节点开启推理段: REASONING_START + REASONING_MESSAGE_START"""
        key = ("reasoning", node_name or "default")
        if self._reasoning_id is not None and key == self._reasoning_key:
            return self._reasoning_id
        self._close_reasoning(events)
        self._reasoning_id = uuid4().hex
        self._reasoning_key = key
        events.append(ReasoningStartEvent(message_id=self._reasoning_id))
        events.append(ReasoningMessageStartEvent(message_id=self._reasoning_id))
        return self._reasoning_id

    def _close_reasoning(self, events: list[BaseEvent]) -> None:
        if self._reasoning_id is None:
            return
        events.append(ReasoningMessageEndEvent(message_id=self._reasoning_id))
        events.append(ReasoningEndEvent(message_id=self._reasoning_id))
        self._reasoning_id = None
        self._reasoning_key = None

    # ── 单条 StreamOne 处理 ─────────────────────

    def _handle_item(self, item: Any, events: list[BaseEvent]) -> None:
        """把一条业务 StreamOne(含 content/node_name/stream_event_type/data)转为事件组"""
        event_type = str(getattr(item, "stream_event_type", "") or "")
        node_name = str(getattr(item, "node_name", "") or "")
        content = str(getattr(item, "content", "") or "")
        data: dict | None = getattr(item, "data", None)

        if event_type == "status":
            # 节点进度: 步骤切换 + 人话提示
            self._open_step(events, node_name)
            events.append(
                CustomEvent(name=CUSTOM_NAME_STATUS, value={"message": content, "node": node_name})
            )

        elif event_type in ("answer", "", "None"):
            if content:
                message_id = self._open_message(events)
                events.append(TextMessageContentEvent(message_id=message_id, delta=content))

        elif event_type in ("llm_thinking", "agent_thinking"):
            if content:
                reasoning_id = self._open_reasoning(events, node_name)
                events.append(ReasoningMessageContentEvent(message_id=reasoning_id, delta=content))

        elif event_type == "agent_thinking_conclusion":
            value = dict(data or {})
            value.setdefault("conclusion", content)
            self._close_reasoning(events)
            self._open_step(events, node_name)
            events.append(CustomEvent(name=CUSTOM_NAME_INTENT_RESULT, value=value))

        elif event_type == "tool_call":
            data = data or {}
            tool_call_id = uuid4().hex
            tool_name = str(data.get("tool_name") or node_name or "knowledge_search")
            events.append(ToolCallStartEvent(tool_call_id=tool_call_id, tool_call_name=tool_name))
            # AG-UI 1.0 的 START 不含 input 字段: 调用入参作为 ARGS 增量下发
            if data.get("request") is not None:
                events.append(ToolCallArgsEvent(tool_call_id=tool_call_id, delta=_dumps(data["request"])))
            events.append(ToolCallEndEvent(tool_call_id=tool_call_id))
            # RESULT: 结构化 results 优先(前端直接消费引用溯源), 回退格式化文本
            result_content = _dumps(data["results"]) if data.get("results") is not None else content
            events.append(
                ToolCallResultEvent(
                    message_id=uuid4().hex, tool_call_id=tool_call_id, content=result_content
                )
            )

        elif event_type == "interaction":
            value = dict(data or {})
            value.setdefault("question", content)
            events.append(CustomEvent(name=CUSTOM_NAME_INTERACTION, value=value))

        elif event_type == "error":
            self._errored = True
            events.append(RunErrorEvent(message=content or "未知错误"))

        else:
            # 未识别的业务事件按自定义事件透传, 不丢弃
            logger.debug(f"AG-UI 转换器忽略未识别事件类型: {event_type}")

    # ── 收尾 ────────────────────────────────────

    def _finalize(self, events: list[BaseEvent]) -> None:
        """正常收尾: 关闭未闭的推理段/正文消息/步骤, 最后 RUN_FINISHED"""
        if self._errored:
            # RUN_ERROR 已发, 不再发 RUN_FINISHED(协议: 错误即运行终态)
            return
        self._close_reasoning(events)
        if self._message_id is not None:
            events.append(TextMessageEndEvent(message_id=self._message_id))
            self._message_id = None
        if self._current_step:
            events.append(StepFinishedEvent(step_name=self._current_step))
            self._current_step = None
        events.append(self._finished())

    # ── 主入口 ──────────────────────────────────

    async def transform(
        self, source: AsyncIterator[Any]
    ) -> AsyncIterator[str]:
        """消费业务 StreamOne 流, 产出 AG-UI 事件 SSE 载荷(JSON 字符串)"""
        # 运行开始(+可选状态快照)
        events: list[BaseEvent] = [self._started()]
        if self._initial_state is not None:
            events.append(StateSnapshotEvent(snapshot=self._initial_state))
        for ev in events:
            yield encode_agui_event(ev)

        try:
            async for item in source:
                batch: list[BaseEvent] = []
                self._handle_item(item, batch)
                for ev in batch:
                    yield encode_agui_event(ev)
            closing: list[BaseEvent] = []
            self._finalize(closing)
            for ev in closing:
                yield encode_agui_event(ev)
        except Exception as e:
            logger.error(f"AG-UI 事件流转换失败: {e}", exc_info=True)
            self._errored = True
            yield encode_agui_event(RunErrorEvent(message=str(e)))


def _dumps(value: Any) -> str:
    """紧凑中文安全 JSON 序列化(工具入参/结果载荷)"""
    return json.dumps(value, ensure_ascii=False)


def normalize_llm_chunk(chunk: Any) -> list[dict]:
    """把 LangChain AIMessageChunk 归一化为 StreamOne 形态的 dict 列表(直连 LLM 对话用)

    - reasoning_content / additional_kwargs.reasoning_content → llm_thinking
    - content → answer
    同一 chunk 可能同时携带思考与正文, 依次产出两条
    """
    items: list[dict] = []

    reasoning = getattr(chunk, "reasoning_content", None)
    if not reasoning:
        additional = getattr(chunk, "additional_kwargs", None)
        if isinstance(additional, dict):
            reasoning = additional.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning:
        items.append(
            {"content": reasoning, "node_name": "", "stream_event_type": "llm_thinking", "data": None}
        )

    content = getattr(chunk, "content", "")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    if content:
        items.append(
            {"content": str(content), "node_name": "", "stream_event_type": "answer", "data": None}
        )
    return items


class _NormalizedItem:
    """与 StreamOne 同构的轻量包装(dict → 属性访问)"""

    def __init__(self, payload: dict):
        self.content = payload.get("content", "")
        self.node_name = payload.get("node_name", "")
        self.stream_event_type = payload.get("stream_event_type")
        self.data = payload.get("data")


async def normalize_llm_source(
    source: AsyncIterator[Any],
) -> AsyncIterator[_NormalizedItem]:
    """直连 LLM 的 chunk 流归一化(供 AguiStreamTransformer 消费)"""
    async for chunk in source:
        for payload in normalize_llm_chunk(chunk):
            yield _NormalizedItem(payload)
