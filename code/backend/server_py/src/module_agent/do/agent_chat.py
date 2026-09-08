from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


class AgentChatRequest(BaseModel):
    """智能体聊天请求(agent 由对话记录的 agent_id 决定, 前端无需传)"""

    message: str


class AgentChatState(MessagesState):
    """智能体聊天 graph 状态(单节点: 按智能体 system_prompt 生成回复)"""

    system_prompt: str
    user_id: str


class AgentSummary(BaseModel):
    """占位结构化模型(预留: 智能体对话标题自动生成)"""

    title: str = Field(default="新对话", description="不超过20字的对话标题")
