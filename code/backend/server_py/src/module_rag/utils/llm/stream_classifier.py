from collections.abc import Generator

from langchain_core.runnables.schema import StreamEvent

from module_rag.do.rag_chat import (
    RagHelpInfo,
    StreamEventType,
    StreamOne,
    NODE_EVENT_MAP,
    NODE_STATUS_MAP,
    GraphEvent,
    GraphNode,
)


# 只允许 chat 节点逐 token 流式输出
# 如果希望意图分析节点也流式输出，可以加入 GraphNode.INTENT.value
_TOKEN_STREAM_NODES: set[str] = {
    GraphNode.CHAT.value,
    GraphNode.INTENT.value
}


def extract_text(content: object) -> str:
    """从 LangChain message content 中提取文本"""
    match content:
        case str():
            return content

        case list():
            parts: list[str] = []

            for block in content:
                if not isinstance(block, dict):
                    continue

                if block.get("type") != "text":
                    continue

                text = block.get("text", "")
                if isinstance(text, str):
                    parts.append(text)

            return "".join(parts)

        case _:
            return ""


class StreamEventClassifier:
    """LangGraph 事件分类器"""

    def _not_allowed_event(self, event: StreamEvent) -> bool:
        """判断是否为图节点根事件，而不是节点内部 Runnable 事件"""
        event_name = event.get("name")
        bool_allowed = event_name in ["RunnableSequence","RunnableLambda"]
        return bool_allowed

    def classify(self, event: StreamEvent) -> Generator[StreamOne, None, None]:
        """将 LangGraph 原始事件转换为业务 StreamOne"""
        event_name = event.get("event") or ""
        if self._not_allowed_event(event):
            return

        if event_name == GraphEvent.MODEL_STREAM:
            yield from self._model_stream(event)

        elif event_name == GraphEvent.NODE_START:
            yield from self._node_start(event)

        elif event_name == GraphEvent.NODE_END:
            yield from self._node_end(event)

    def _model_stream(self, event: StreamEvent) -> Generator[StreamOne, None, None]:
        """处理 LLM token 事件"""
        node_name = self._node_name(event)

        if node_name not in _TOKEN_STREAM_NODES:
            return

        chunk = self._event_data(event).get("chunk")
        if not chunk:
            return

        if reasoning := self._reasoning_text(chunk):
            yield StreamOne(
                content=reasoning,
                node_name=node_name,
                stream_event_type=StreamEventType.LLM_THINKING,
            )

        if content := self._content_text(chunk):
            yield StreamOne(
                content=content,
                node_name=node_name,
                stream_event_type=NODE_EVENT_MAP.get(
                    node_name,
                    StreamEventType.ANSWER,
                ),
            )

    def _node_start(self, event: StreamEvent) -> Generator[StreamOne, None, None]:
        """处理节点开始事件"""
        
        node_name = self._node_name(event)
        if text := NODE_STATUS_MAP.get(node_name):
            yield StreamOne(
                content=text,
                node_name=node_name,
                stream_event_type=StreamEventType.STATUS,
            )

    def _node_end(self, event: StreamEvent) -> Generator[StreamOne, None, None]:
        """处理节点结束事件"""
        node_name = self._node_name(event)
        output = self._event_output(event)

        if node_name == GraphNode.INTENT:
            info: RagHelpInfo | None = output.get("rag_help_info")

            if info:
                yield StreamOne(
                    content=self._format_intent(info),
                    node_name=node_name,
                    stream_event_type=StreamEventType.AGENT_THINKING_CONCLUSION,
                )

        elif node_name == GraphNode.SEARCH:
            yield StreamOne(
                content=self._format_search(output),
                node_name=node_name,
                stream_event_type=StreamEventType.TOOL_CALL,
            )

    @staticmethod
    def _event_data(event: StreamEvent) -> dict:
        """读取事件 data"""
        data = event.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _event_output(event: StreamEvent) -> dict:
        """读取节点输出"""
        data = event.get("data")
        if not isinstance(data, dict):
            return {}

        output = data.get("output")
        return output if isinstance(output, dict) else {}

    @staticmethod
    def _node_name(event: StreamEvent) -> str:
        """读取节点名"""
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            return ""

        node_name = metadata.get("langgraph_node")
        return node_name if isinstance(node_name, str) else ""

    @staticmethod
    def _content_text(chunk: object) -> str:
        """读取回答内容"""
        return extract_text(getattr(chunk, "content", ""))

    @staticmethod
    def _reasoning_text(chunk: object) -> str:
        """读取推理内容"""
        reasoning = getattr(chunk, "reasoning_content", None)

        if not reasoning:
            additional = getattr(chunk, "additional_kwargs", None)
            if not isinstance(additional, dict):
                additional = {}

            reasoning = additional.get("reasoning_content")

        return reasoning if isinstance(reasoning, str) else ""

    @staticmethod
    def _format_intent(info: RagHelpInfo) -> str:
        """格式化意图分析结果"""
        return f"""意图: {info.intent}
        需要检索: {info.is_need_external_info}"""

    @staticmethod
    def _format_search(output: dict) -> str:
        """格式化知识库检索结果"""
        knowledge_context_list = output.get("knowledge_context_list") or []

        hit_count = len(knowledge_context_list)

        return f"检索到 {hit_count} 条相关片段"
