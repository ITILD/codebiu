from pydantic import BaseModel, Field, field_validator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


class Message(BaseModel):
    """消息模型，与langchain_core.messages兼容"""

    role: str = Field(..., description="消息角色：system、user、assistant")
    content: str = Field(..., description="消息内容")
    additional_kwargs: dict = Field(default_factory=dict)

    @classmethod
    def from_langchain_message(cls, msg: BaseMessage) -> "Message":
        """从 LangChain 消息创建 Message 对象"""
        role_mapping = {"human": "user", "ai": "assistant", "system": "system"}

        role = role_mapping.get(msg.type, msg.type)
        return cls(
            role=role,
            content=str(msg.content),
            additional_kwargs=getattr(msg, "additional_kwargs", {}),
        )

    def to_langchain_message(self) -> BaseMessage:
        """转换为 LangChain 消息对象"""
        role_mapping = {
            "user": HumanMessage,
            "assistant": AIMessage,
            "system": SystemMessage,
        }

        msg_class = role_mapping.get(self.role, HumanMessage)
        return msg_class(content=self.content, additional_kwargs=self.additional_kwargs)


class ChatRequest(BaseModel):
    """聊天请求模型"""

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    messages: list[Message] = Field(..., description="消息内容")
    streaming: bool = Field(False, description="是否启用流式响应")

    @field_validator("messages", mode="before")
    @classmethod
    def validate_messages(cls, v):
        """
        验证并标准化messages字段
        - 如果是字符串，自动转换为包含单个用户消息的列表
        - 如果是列表，保持原样
        """
        if isinstance(v, str):
            # 将字符串转换为包含单个用户消息的列表
            return [Message(role="user", content=v)]


class EmbeddingRequest(BaseModel):
    """嵌入请求模型"""

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    texts: list[str] = Field(..., description="待嵌入的文本列表")


class CacheClearRequest(BaseModel):
    """缓存清除请求模型"""

    model_id: str | None = Field(
        None, description="模型配置ID或模型标识名称，为空则清除所有缓存"
    )
