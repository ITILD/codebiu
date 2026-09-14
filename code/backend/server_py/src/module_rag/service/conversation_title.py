"""会话标题自动生成: 首次问答结束后用 LLM 概括生成标题, 替换前端预填的占位标题"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from module_rag.dao.rag_chat_prompt import SUMMARIZE_SYSTEM_PROMPT
from module_rag.do.conversation import ConversationUpdate
from module_rag.do.rag_chat import ConversationSummary
from module_rag.service.chat_message import ChatMessageService
from module_rag.service.conversation import ConversationService
from module_rag.service.user_model import UserModelService

logger = logging.getLogger(__name__)

# 标题最大长度(与会话列表展示/前端预填截断保持一致)
TITLE_MAX_LEN = 20


async def maybe_auto_title(
    conversation_id: str,
    user_id: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """首次问答后自动生成会话标题(仅首轮消息时执行, 失败静默不影响主流程)

    :param conversation_id: 会话ID
    :param user_id: 用户ID(用于解析可用对话模型)
    :param user_message: 首条用户提问
    :param assistant_message: 首条助手回答
    """
    try:
        conversation_service = ConversationService()
        chat_message_service = ChatMessageService()
        conv = await conversation_service.get(conversation_id)
        if conv is None:
            return
        original_title = conv.title
        # 仅首轮问答(1条用户消息+1条助手消息)后生成, 后续轮次不再改动标题
        total = await chat_message_service.count_by_conversation(conversation_id)
        if total != 2:
            return
        llm = await UserModelService().get_llm_by_user_id(user_id, streaming=False)
        if llm is None:
            logger.warning(f"用户 {user_id} 无可用对话模型, 跳过自动生成会话标题")
            return
        structured = llm.with_structured_output(ConversationSummary)
        result: ConversationSummary = await structured.ainvoke(
            [
                SystemMessage(content=SUMMARIZE_SYSTEM_PROMPT),
                HumanMessage(
                    content=f"用户提问: {user_message[:2000]}\n助手回答: {assistant_message[:2000]}"
                ),
            ]
        )
        title = (result.title or "").strip()[:TITLE_MAX_LEN]
        if not title:
            return
        # 生成期间用户手动改名/删除会话则不覆盖
        conv_now = await conversation_service.get(conversation_id)
        if conv_now is None or conv_now.title != original_title:
            return
        await conversation_service.update(
            conversation_id, ConversationUpdate(title=title)
        )
    except Exception as e:
        logger.warning(f"自动生成会话标题失败 conversation_id={conversation_id}: {e}")
