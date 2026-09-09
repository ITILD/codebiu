"""消息列表 token 裁剪工具

按 token 上限裁剪历史消息: 从最新消息向前累计,超限时丢弃更早的消息,
保证最近上下文完整送入 LLM(旧上下文信息密度低,优先舍弃)。
"""
import logging

from langchain_core.messages import BaseMessage

from module_ai.utils.llm.utils.llm_utils import LLMUtils

logger = logging.getLogger(__name__)

# 默认裁剪上限(约 16k token,适配主流模型上下文窗口并留出生成空间)
DEFAULT_MAX_TOKENS = 16000


def messages_trim_with_max_tokens(
    messages: list[BaseMessage], max_tokens: int = DEFAULT_MAX_TOKENS
) -> list[BaseMessage]:
    """按 token 上限裁剪消息列表(保留最近的消息)

    :param messages: 原始消息列表(按时间升序)
    :param max_tokens: token 上限
    :return: 裁剪后的新列表(不修改原列表;至少保留最后一条消息)
    """
    if not messages:
        return []

    result: list[BaseMessage] = []
    total = 0
    # 从最新消息向前累计,超限即停止
    for msg in reversed(messages):
        tokens = LLMUtils.count_tokens(str(getattr(msg, "content", "")))
        if total + tokens > max_tokens and result:
            break
        result.append(msg)
        total += tokens

    result.reverse()
    if len(result) < len(messages):
        logger.debug(
            f"消息裁剪: {len(messages)} -> {len(result)} (tokens={total}/{max_tokens})"
        )
    return result
