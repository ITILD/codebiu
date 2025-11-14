from sqlmodel import Column, DateTime, Field, SQLModel, JSON
from uuid import uuid4
from datetime import datetime, timezone
from module_ai.utils.llm.do.model_type import ModelType, ModelServerType


class ModelConfigBase(SQLModel):
    """
    模型配置基础模型
    """

    model_type: ModelType = Field(ModelType.CHAT, description="模型类型")
    # type openai  vllm 枚举
    server_type: ModelServerType = Field(
        ModelServerType.OPENAI, description="模型服务类型"
    )
    # 模型标识
    model: str = Field(..., description="模型标识名称")
    url: str | None = Field(None, description="API基础URL")
    api_key: str | None = Field(None, description="API访问密钥")

    # 成本
    pay_in: float | None = Field(0.0, ge=0, description="模型调用成本")
    pay_out: float | None = Field(0.0, ge=0, description="模型输出成本")

    # 配置
    input_tokens: int | None = Field(8192, description="输入最大token数")
    out_tokens: int | None = Field(8192, gt=0, description="生成最大token数/向量化模型是维度")
    temperature: float | None = Field(0.7, ge=0, le=2, description="生成温度系数")
    timeout: int | None = Field(60, gt=0, description="请求超时时间(秒)")
    no_think: bool | None  = Field(False, description="是否禁用思考 默认否不考虑")
    # 其余配置统一放在json字段中,使用时遍历
    extra: dict | None = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),  # ！
        description="额外配置",
    )


class ModelConfig(ModelConfigBase, table=True):
    """
    模型配置数据库模型
    """

    user_id: str = Field(..., description="用户ID")
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )


class ModelConfigCreateRequest(ModelConfigBase):
    """
    创建模型配置的请求模型
    """

    pass


class ModelConfigCreate(ModelConfigCreateRequest):
    """
    创建模型配置的添加模型
    """

    user_id: str = Field(..., description="用户ID")


class ModelConfigUpdate(SQLModel):
    """
    更新模型配置的请求模型
    """
    model_type: ModelType | None = None
    # type openai  vllm 枚举
    server_type: ModelServerType | None = None
    # 模型标识
    model: str = None
    url: str | None = None
    api_key: str | None = None

    # 成本
    pay_in: float | None = None
    pay_out: float | None = None

    # 配置
    input_tokens: int | None = None
    out_tokens: int | None = None
    temperature: float | None = None
    timeout: int | None = None
    no_think: bool | None = None
    # 其余配置统一放在json字段中,使用时遍历
    extra: dict | None = None
