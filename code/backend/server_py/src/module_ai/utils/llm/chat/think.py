"""LLM 思考(think/reasoning)相关工具

- ChatQwenWithReasoning: 兼容 OpenAI 协议中 reasoning_content 思考字段的 Chat 模型
- NoThinkTagsParser: 移除 <think></think> 标签及内容的输出解析器(支持流式)
"""
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import BaseTransformOutputParser
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI


class ChatQwenWithReasoning(ChatOpenAI):
    """同时支持流式/非流式提取 reasoning_content 的 ChatOpenAI 子类

    Qwen 等模型的思考内容通过 delta.reasoning_content 下发(非 OpenAI 标准字段),
    LangChain 默认会丢弃; 此处拦截 chunk 转换过程将其挂回 message。
    """

    # 流式: 拦截 _convert_chunk_to_generation_chunk
    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """从流式 chunk 中提取 reasoning_content"""
        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if gen_chunk is None:
            return None

        # 从原始 chunk dict 的 delta 中提取非标准字段
        choices = chunk.get("choices", [])
        if choices and isinstance(choices[0].get("delta"), dict):
            reasoning = choices[0]["delta"].get("reasoning_content")
            if reasoning:
                gen_chunk.message.reasoning_content = reasoning

        return gen_chunk


class NoThinkTagsParser(BaseTransformOutputParser):
    """移除所有 <think></think> 标签及其内容的输出解析器

    - 移除 content 内所有 <think>...</think> 标签及标签间内容, 保留其余文本
    - 支持同步/异步、流式/非流式(内部按缓冲区分段处理)

    示例:
        输入: "正常文本<think>移除内容</think>保留文本"
        输出: "正常文本保留文本"
    """

    def __init__(self):
        super().__init__()
        self._buffer = ""
        # 当前是否处于 think 标签之外
        self._out_tag = True

    def parse(self, text):
        out_tag, _in_tag = self._process_buffer(text)
        return out_tag

    def _process_buffer(self, buffer: str):
        """流式缓冲区分段处理

        :return: (可安全输出的内容, 需要保留的临时内容)
        """
        open_pos = buffer.find("<think>")
        close_pos = buffer.rfind("</think>")

        # 不在标签内且没有开始标签: 全部可直接输出
        if self._out_tag and open_pos == -1:
            return buffer, ""

        # 出现开始标签
        if open_pos != -1:
            if close_pos == -1:
                # 未闭合: 开始标签之前可输出, 其余进缓冲
                self._out_tag = False
                return buffer[:open_pos], buffer[open_pos:]
            # 已闭合: 剔除标签及内容
            self._out_tag = True
            return buffer[:open_pos] + buffer[close_pos + 8:], buffer[open_pos : close_pos + 8]

        # 遇到结束标签(且当前在标签内): 丢弃标签前内容
        if close_pos != -1 and not self._out_tag:
            self._out_tag = True
            return buffer[close_pos + 8:], ""

        # 默认: 无可输出内容
        return "", ""

    def get_no_think_runnable(self) -> RunnableLambda:
        """前置 Runnable: 在首条 system 消息(或文本)开头追加 /no_think 指令"""

        def add_no_think_prefix(input_data):
            """在消息列表首条或纯文本前添加 /no_think 前缀"""
            if isinstance(input_data, list) and input_data:
                messages = input_data.copy()
                first = messages[0]
                if isinstance(first, dict) and "content" in first:
                    first["content"] = f"/no_think {first['content']}"
                elif isinstance(first, BaseMessage) and hasattr(first, "content"):
                    first.content = f"/no_think {first.content}"
                return messages
            return f"/no_think {str(input_data)}"

        return RunnableLambda(add_no_think_prefix)
