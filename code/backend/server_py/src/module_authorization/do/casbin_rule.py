from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Column, DateTime
from datetime import datetime, timezone


class CasbinRuleBase(SQLModel):
    """Casbin规则基础模型（不含数据库表配置）"""
    ptype: str = Field(default="", max_length=255, description="策略类型")
    v0: str = Field(default="", max_length=255, description="主体")
    v1: str = Field(default="", max_length=255, description="对象")
    v2: str = Field(default="", max_length=255, description="动作")
    v3: str = Field(default="", max_length=255, description="额外字段1")
    v4: str = Field(default="", max_length=255, description="额外字段2")
    v5: str = Field(default="", max_length=255, description="额外字段3")


class CasbinRule(CasbinRuleBase, table=True):
    """Casbin规则数据库模型（对应数据库表）"""
    __tablename__ = "casbin_rule"
    __table_args__ = {'extend_existing': True}
    
    id: int = Field(
        default=None,
        primary_key=True,
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


class CasbinRuleCreate(CasbinRuleBase):
    """创建Casbin规则的请求模型"""
    pass


class CasbinRuleUpdate(CasbinRuleBase):
    """更新Casbin规则的请求模型"""
    pass


class CasbinRuleResponse(CasbinRuleBase):
    """Casbin规则响应模型"""
    
    id: int = Field(..., description="唯一标识符")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    
    

# 策略模型
class PolicyBase(BaseModel):
    """添加策略请求模型"""
    sub: str  # 主体（用户或角色）
    obj: str  # 对象（资源）
    act: str  # 动作（操作）
    
    
# 请求模型
class PolicyRequest(PolicyBase):
    """添加策略请求模型"""
    pass

class RoleForUserRequest(BaseModel):
    """为用户添加角色请求模型"""
    user_id: str  # 用户ID
    role_key: str  # 角色键


class BatchAddRolePermissionsRequest(BaseModel):
    """批量添加角色权限请求模型"""
    role_key: str  # 角色键
    permissions: list[dict[str, str]]  # 权限列表，每项包含permission_code和method


class BatchAddUserRolesRequest(BaseModel):
    """批量添加用户角色请求模型"""
    user_id: str  # 用户ID
    role_keys: list[str]  # 角色键列表


# 响应模型
class PermissionCheckResponse(BaseModel):
    """权限检查响应模型"""
    has_permission: bool  # 是否有权限


class PolicyResponse(PolicyBase):
    """策略响应模型"""
    pass


class RolePermissionResponse(BaseModel):
    """角色权限响应模型"""
    role_key: str  # 角色键
    permissions: list[dict[str, str]]  # 权限列表

class CheckPermissionRequest(BaseModel):
    user_id: str
    obj: str
    act: str