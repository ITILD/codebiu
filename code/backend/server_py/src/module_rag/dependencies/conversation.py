from fastapi import Depends
from module_rag.dao.conversation import ConversationDao
from module_rag.dao.chat_message import ChatMessageDao
from module_rag.service.conversation import ConversationService
from module_rag.service.chat_message import ChatMessageService


async def get_conversation_dao():
    return ConversationDao()


async def get_chat_message_dao():
    return ChatMessageDao()


async def get_conversation_service(
    conv_dao: ConversationDao = Depends(get_conversation_dao),
    msg_dao: ChatMessageDao = Depends(get_chat_message_dao),
):
    return ConversationService(conv_dao, msg_dao)


async def get_chat_message_service(
    msg_dao: ChatMessageDao = Depends(get_chat_message_dao),
):
    return ChatMessageService(msg_dao)
