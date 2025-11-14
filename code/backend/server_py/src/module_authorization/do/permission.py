from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class PermissionBase(SQLModel):
    """权限基础模型（不含数据库表配置）"""
    
    name: str = Field(..., max_length=100, description="权限名称")
    code: str = Field(..., max_length=100, description="权限代码")
    description: str | None = Field( max_length=255, description="权限描述")
    resource_type: str | None = Field( max_length=50, description="资源类型")
    action: str | None = Field( max_length=20, description="操作类型")
    parent_id: str | None = Field( description="父权限ID")
    is_active: bool = Field(default=True, description="是否激活")


class Permission(PermissionBase, table=True):
    """权限数据库模型（对应数据库表）"""
    
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


class PermissionCreate(PermissionBase):
    """创建权限的请求模型"""
    pass


class PermissionUpdate(PermissionBase):
    """更新权限的请求模型"""
    
    pass


class PermissionResponse(SQLModel):
    """权限响应模型"""
    
    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="权限名称")
    code: str = Field(..., description="权限代码")
    description: str | None = Field( description="权限描述")
    resource_type: str | None = Field( description="资源类型")
    action: str | None = Field( description="操作类型")
    parent_id: str | None = Field( description="父权限ID")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")