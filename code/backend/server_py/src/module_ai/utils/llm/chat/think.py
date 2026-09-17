"""LLM 思考(think/reasoning)相关工具

- ChatQwenWithReasoning: 兼容 OpenAI 协议中 reasoning_content 思考字段的 Chat 模型
- NoThinkTagsParser: 移除 <think></think> 标签及内容的输出解析器(支持流式)
"""
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel, BaseMessage
from langchain_core.output_parsers import BaseTransformOutputParser
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from openai import BadRequestError

logger = logging.getLogger(__name__)

# "始终思考, 不支持关闭思考"类错误特征(如 GLM 系列返回的 400/code=1210)
_ALWAYS_THINK_HINT = "不支持关闭思考"

# 思考深度档位 → 思考预算 token 数(off 不需要预算; 厂商不支持预算字段时自动忽略)
THINK_BUDGETS: dict[str, int] = {
    "low": 4096,
    "medium": 8192,
    "high": 16384,
}


def with_think_mode(model: BaseChatModel, mode: str) -> BaseChatModel:
    """按思考模式克隆 chat 模型(off=关闭思考, low/medium/high=开启并设思考预算)

    :param model: 已构建的 chat 模型实例
    :param mode: off / low / medium / high
    :return: 调整过思考配置的模型(非 OpenAI 兼容协议模型原样返回)
    """
    if not isinstance(model, ChatQwenWithReasoning):
        return model
    extra = {**(model.extra_body or {})}
    if mode == "off":
        # 始终思考模型(如 GLM 系列)关闭被拒时由请求层自动回退开启思考
        extra["enable_thinking"] = False
    else:
        extra["enable_thinking"] = True
        if mode in THINK_BUDGETS:
            extra["thinking_budget"] = THINK_BUDGETS[mode]
    return model.model_copy(update={"extra_body": extra})

# 已确认始终思考的模型注册表(key=(base_url, model_name)):
# 命中后不再尝试关闭思考(结构化输出强制工具调用直接以开启思考请求, 避免每轮多一次失败请求)
_ALWAYS_THINK_MODELS: set[tuple[str, str]] = set()


def _is_always_think_error(error: Exception) -> bool:
    """识别"该模型始终思考, 不支持关闭思考"类 400 错误"""
    return _ALWAYS_THINK_HINT in str(error)


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

    @staticmethod
    def _is_forced_tool_choice(tool_choice: Any) -> bool:
        """判断是否强制指定工具(required/any/True/指定工具名或对象)

        auto/none/None/False 交给模型自选, 不属于强制调用
        """
        return tool_choice not in (None, False, "auto", "none")

    def _think_key(self) -> tuple[str, str]:
        """模型唯一键(base_url, model_name), 用于始终思考模型注册表"""
        return (
            str(getattr(self, "openai_api_base", "") or ""),
            str(getattr(self, "model_name", "") or ""),
        )

    def _wants_think_off(self) -> bool:
        """当前配置是否要求关闭思考(extra_body.enable_thinking=False)"""
        return (self.extra_body or {}).get("enable_thinking") is False

    def _with_think_on(self) -> "ChatQwenWithReasoning":
        """复制实例并开启思考(始终思考模型回退用)"""
        return self.model_copy(
            update={"extra_body": {**(self.extra_body or {}), "enable_thinking": True}}
        )

    def _before_request_maybe_retry(self, error: Exception) -> bool:
        """始终思考模型关闭思考被拒时登记注册表

        :return: True 表示已登记(调用方应以开启思考重试), False 表示与思考无关
        """
        if _is_always_think_error(error):
            _ALWAYS_THINK_MODELS.add(self._think_key())
            logger.warning(
                "模型始终思考不支持关闭思考(%s/%s), 已改用开启思考重试",
                self._think_key()[0], self._think_key()[1],
            )
            return True
        return False

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """非流式生成: 关闭思考被拒(始终思考模型)时回退开启思考重试"""
        if self._wants_think_off() and self._think_key() not in _ALWAYS_THINK_MODELS:
            try:
                return super()._generate(messages, stop, run_manager, **kwargs)
            except BadRequestError as e:
                if self._before_request_maybe_retry(e):
                    return self._with_think_on()._generate(messages, stop, run_manager, **kwargs)
                raise
        return super()._generate(messages, stop, run_manager, **kwargs)

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        """异步非流式生成: 关闭思考被拒(始终思考模型)时回退开启思考重试"""
        if self._wants_think_off() and self._think_key() not in _ALWAYS_THINK_MODELS:
            try:
                return await super()._agenerate(messages, stop, run_manager, **kwargs)
            except BadRequestError as e:
                if self._before_request_maybe_retry(e):
                    return await self._with_think_on()._agenerate(
                        messages, stop, run_manager, **kwargs
                    )
                raise
        return await super()._agenerate(messages, stop, run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """流式生成: 关闭思考被拒(始终思考模型)时回退开启思考重试"""
        if self._wants_think_off() and self._think_key() not in _ALWAYS_THINK_MODELS:
            try:
                yield from super()._stream(messages, stop, run_manager, **kwargs)
                return
            except BadRequestError as e:
                if self._before_request_maybe_retry(e):
                    yield from self._with_think_on()._stream(
                        messages, stop, run_manager, **kwargs
                    )
                    return
                raise
        yield from super()._stream(messages, stop, run_manager, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        """异步流式生成: 关闭思考被拒(始终思考模型)时回退开启思考重试"""
        if self._wants_think_off() and self._think_key() not in _ALWAYS_THINK_MODELS:
            try:
                async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
                    yield chunk
                return
            except BadRequestError as e:
                if self._before_request_maybe_retry(e):
                    async for chunk in self._with_think_on()._astream(
                        messages, stop, run_manager, **kwargs
                    ):
                        yield chunk
                    return
                raise
        async for chunk in super()._astream(messages, stop, run_manager, **kwargs):
            yield chunk

    def bind_tools(
        self,
        tools: list | tuple | dict | BaseTool,
        **kwargs: Any,
    ) -> Runnable:
        """重写工具绑定: 思考模式下出现强制 tool_choice 时, 该次调用自动关闭思考

        DashScope 思考模式(enable_thinking=True)不支持强制 tool_choice
        (required 或指定工具对象), 直接触发 400:
        "The tool_choice parameter does not support being set to required or object
        in thinking mode"(结构化输出 create_agent/with_structured_output 均会强制)。
        普通工具调用(tool_choice=auto)与思考模式兼容, 不受影响。

        例外: 已登记的"始终思考"模型(如 GLM 系列, 关闭思考直接 400/code=1210)
        跳过关闭思考, 由请求层回退逻辑保证强制工具调用可用。
        """
        if (
            (self.extra_body or {}).get("enable_thinking")
            and self._think_key() not in _ALWAYS_THINK_MODELS
            and self._is_forced_tool_choice(kwargs.get("tool_choice"))
        ):
            # 复制实例并关闭思考后重绑, 保证强制工具调用(结构化输出)可用
            cloned = self.model_copy(
                update={"extra_body": {**(self.extra_body or {}), "enable_thinking": False}}
            )
            return cloned.bind_tools(tools, **kwargs)
        return super().bind_tools(tools, **kwargs)


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
