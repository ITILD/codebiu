from pydantic import BaseModel
# from sqlmodel import SQLModel, Field, Column, DateTime
# from datetime import datetime, timezone
# from uuid import uuid4

# class CasbinRuleBase(SQLModel):
#     """Casbin规则基础模型(不含数据库表配置)"""
#     ptype: str = Field(default="", max_length=255, description="策略类型")
#     v0: str = Field(default="", max_length=255, description="主体")
#     v1: str = Field(default="", max_length=255, description="域")
#     v2: str = Field(default="", max_length=255, description="对象")
#     v3: str = Field(default="", max_length=255, description="动作")
#     v4: str = Field(default="", max_length=255, description="额外字段")
#     v5: str = Field(default="", max_length=255, description="额外字段")    

# 策略模型
class PolicyBase(BaseModel):
    """添加策略请求模型"""
    sub: str  # 主体(用户或角色)
    dom: str  # 域(项目ID或"*"表示全局)
    obj: str  # 对象(资源)
    act: str  # 动作(操作)
    
    
# 请求模型
class PolicyRequest(PolicyBase):
    """添加策略请求模型"""
    pass

class RoleForUserRequest(BaseModel):
    """为用户添加角色请求模型"""
    user_id: str  # 用户ID
    role_key: str  # 角色键
    dom: str = "*"  # 域(项目ID或"*"表示全局，默认为全局)


class BatchAddRolePermissionsRequest(BaseModel):
    """批量添加角色权限请求模型"""
    role_key: str  # 角色键
    dom: str = "*"  # 域(项目ID或"*"表示全局，默认为全局)
    permissions: list[dict[str, str]]  # 权限列表，每项包含permission_code和method


class BatchAddUserRolesRequest(BaseModel):
    """批量添加用户角色请求模型"""
    user_id: str  # 用户ID
    role_keys: list[str]  # 角色键列表
    dom: str = "*"  # 域(项目ID或"*"表示全局，默认为全局)


class RolePermsSyncRequest(BaseModel):
    """角色权限全量同步请求模型(角色授权界面提交勾选的权限码)"""
    role_key: str  # 角色键
    codes: list[str]  # 勾选的权限码列表(按钮级权限码自动解析为casbin策略)


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
    """权限检查请求模型"""
    user_id: str  # 用户ID
    dom: str  # 域(项目ID或"*"表示全局)
    obj: str  # 对象(资源)
    act: str  # 动作(操作)