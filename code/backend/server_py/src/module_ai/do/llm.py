from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from module_ai.utils.llm.types import RoleType, LCRoleType, ModelType

class Message(BaseModel):
    """消息模型，与langchain_core.messages兼容"""

    role: RoleType = Field(
        RoleType.USER, description="消息角色：system、user、assistant"
    )
    content: str = Field(..., description="消息内容")
    additional_kwargs: dict = Field(default_factory=dict)

    @classmethod
    def from_langchain_message(cls, msg: BaseMessage) -> "Message":
        """从 LangChain 消息创建 Message 对象"""
        role_mapping = {
            LCRoleType.USHUMAN: RoleType.USER,
            LCRoleType.AI: RoleType.ASSISTANT,
            LCRoleType.SYSTEM: RoleType.SYSTEM,
        }

        role = role_mapping.get(msg.type, msg.type)
        return cls(
            role=role,
            content=str(msg.content),
            additional_kwargs=getattr(msg, "additional_kwargs", {}),
        )

    def to_langchain_message(self) -> BaseMessage:
        """转换为 LangChain 消息对象"""
        role_mapping = {
            RoleType.USER: HumanMessage,
            RoleType.ASSISTANT: AIMessage,
            RoleType.SYSTEM: SystemMessage,
        }

        msg_class = role_mapping.get(self.role, HumanMessage)
        return msg_class(content=self.content, additional_kwargs=self.additional_kwargs)


class ChatRequest(BaseModel):
    """聊天请求模型"""

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    messages: str | list[BaseMessage] = Field(
        ..., description="消息内容(字符串或消息列表, 列表项可为 dict/Message/LangChain 消息)"
    )
    streaming: bool = Field(False, description="是否启用流式响应")

    @field_validator("messages", mode="before")
    @classmethod
    def validate_messages(cls, v):
        """
        验证并标准化messages字段(统一转为 LangChain 消息, 供模型直接调用)
        - 字符串 → 单条用户消息列表
        - 列表项为 dict/pydantic Message → 转 LangChain 消息
        - 空列表/其他形态保持原样(交由后续校验报错, 避免下标越界)
        """
        if isinstance(v, str):
            return [HumanMessage(content=v)]
        if isinstance(v, list):
            converted: list = []
            for item in v:
                if isinstance(item, BaseMessage):
                    converted.append(item)
                elif isinstance(item, Message):
                    converted.append(item.to_langchain_message())
                elif isinstance(item, dict):
                    converted.append(Message(**item).to_langchain_message())
                else:
                    converted.append(item)
            return converted
        return v


class EmbeddingRequest(BaseModel):
    """嵌入请求模型"""

    model_id: str = Field(..., description="模型配置ID或模型标识名称")
    texts: list[str] = Field(..., description="待嵌入的文本列表")


class CacheClearRequest(BaseModel):
    """缓存清除请求模型"""

    model_id: str | None = Field(
        None, description="模型配置ID或模型标识名称，为空则清除所有缓存"
    )


class ModelChatCheckFormat(BaseModel):
    """
    校验模型格式化能力的模型
    """

    name: str = Field(..., description="名字")
    age: int = Field(..., description="年龄")


class ModelConfigCheckResponse(BaseModel):
    """
    校验模型配置的响应模型
    """

    is_valid: bool = Field(False, description="模型配置是否有效")
    is_format: bool = Field(False, description="模型支持格式化")


# 各模型类型支持的能力测试项: capability -> 中文名(与前端 capabilityOptionsFor 对齐)
MODEL_CAPABILITIES: dict[str, list[tuple[str, str]]] = {
    ModelType.CHAT.value: [("chat", "问答"), ("structured", "结构化"), ("vision", "多模态")],
    ModelType.EMBEDDINGS.value: [("embedding", "向量化")],
    ModelType.RERANK.value: [("rerank", "重排")],
}


class ModelCapabilityTestItem(BaseModel):
    """单项能力测试结果"""

    capability: str = Field(..., description="能力标识(chat/structured/vision/embedding/rerank)")
    label: str = Field("", description="能力中文名")
    ok: bool = Field(False, description="是否通过")
    detail: str = Field("", description="结果摘要(通过时展示)")
    error: str = Field("", description="失败原因")
    elapsed: float = Field(0.0, description="耗时(秒)")
    suggest: dict | None = Field(
        None, description="附加建议(rerank: 检测到的分数范围与建议配置 score_min/score_max)"
    )


class ModelTestRequest(BaseModel):
    """模型能力测试请求"""

    model_id: str = Field(..., description="模型配置ID")
    capability: str | None = Field(None, description="仅测试指定能力(缺省测试该类型全部能力)")


class ModelTestResponse(BaseModel):
    """模型能力测试响应(结果已持久化到 model_config.check_result)"""

    model_id: str = Field(..., description="模型配置ID")
    model_type: str = Field(..., description="模型类型")
    capabilities: list[ModelCapabilityTestItem] = Field(default_factory=list, description="各项能力测试结果")
    checked_at: datetime | None = Field(None, description="测试时间")
