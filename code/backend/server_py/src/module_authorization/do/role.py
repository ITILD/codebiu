from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class RoleBase(SQLModel):
    """角色基础模型（不含数据库表配置）"""
    
    name: str = Field(..., max_length=50, description="角色名称")
    description: str | None = Field( max_length=255, description="角色描述")
    is_active: bool = Field(default=True, description="是否激活")


class Role(RoleBase, table=True):
    """角色数据库模型（对应数据库表）"""
    
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,  # 主键
        index=True,  # 索引
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
            onupdate=lambda: datetime.now(timezone.utc),  # 自动更新
            nullable=False,  # 不允许为空
        ),
        description="最后更新时间",
    )


class RoleCreate(RoleBase):
    """创建角色的请求模型"""
    pass


class RoleUpdate(RoleBase):
    """更新角色的请求模型"""
    
    pass


class RoleResponse(SQLModel):
    """角色响应模型"""
    
    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="角色名称")
    description: str | None = Field( description="角色描述")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")