"""chat 对话链路工具

- think: 思考模型适配(reasoning_content 保留)与 <think> 标签解析
- trim: 消息列表 token 裁剪(保留最近上下文)
- parsers: 输入 token 限制/超长文本 map-reduce 压缩
- utils: token 计数/文本清洗/向量工具(LLMUtils)
"""
from module_ai.utils.llm.chat.parsers import TokenLimitParser, TooLongRunnable
from module_ai.utils.llm.chat.think import ChatQwenWithReasoning, NoThinkTagsParser
from module_ai.utils.llm.chat.trim import messages_trim_with_max_tokens
from module_ai.utils.llm.chat.utils import LLMUtils

__all__ = [
    "LLMUtils",
    "messages_trim_with_max_tokens",
    "TokenLimitParser",
    "TooLongRunnable",
    "ChatQwenWithReasoning",
    "NoThinkTagsParser",
]
