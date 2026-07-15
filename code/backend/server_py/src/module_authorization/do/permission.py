from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class PermissionBase(SQLModel):
    """权限基础模型(不含数据库表配置)"""

    parent_id: str | None = Field(default="0", description="父权限ID, 0表示根节点")
    name: str = Field(..., max_length=100, description="权限/菜单名称")
    code: str = Field(..., max_length=100, description="权限代码")
    description: str | None = Field(default=None, max_length=255, description="权限描述")
    menu_type: str = Field(default="C", max_length=1, description="菜单类型: M=目录 C=菜单 F=按钮")
    path: str | None = Field(default=None, max_length=200, description="路由路径")
    component: str | None = Field(default=None, max_length=255, description="组件路径")
    perms: str | None = Field(default=None, max_length=100, description="权限标识(如system:user:list)")
    icon: str | None = Field(default=None, max_length=100, description="图标")
    order_num: int = Field(default=0, description="显示顺序")
    visible: bool = Field(default=True, description="是否可见")
    is_active: bool = Field(default=True, description="是否激活")


class Permission(PermissionBase, table=True):
    """权限数据库模型(对应数据库表)"""
    __tablename__ = "permission"
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


class PermissionCreate(PermissionBase):
    """创建权限的请求模型"""
    pass


class PermissionUpdate(SQLModel):
    """更新权限的请求模型"""

    parent_id: str | None = Field(None, description="父权限ID")
    name: str | None = Field(None, max_length=100, description="权限/菜单名称")
    code: str | None = Field(None, max_length=100, description="权限代码")
    description: str | None = Field(None, max_length=255, description="权限描述")
    menu_type: str | None = Field(None, description="菜单类型")
    path: str | None = Field(None, max_length=200, description="路由路径")
    component: str | None = Field(None, max_length=255, description="组件路径")
    perms: str | None = Field(None, max_length=100, description="权限标识")
    icon: str | None = Field(None, max_length=100, description="图标")
    order_num: int | None = Field(None, description="显示顺序")
    visible: bool | None = Field(None, description="是否可见")
    is_active: bool | None = Field(None, description="是否激活")


class PermissionResponse(SQLModel):
    """权限响应模型"""

    id: str = Field(..., description="唯一标识符")
    parent_id: str | None = Field(description="父权限ID")
    name: str = Field(..., description="权限/菜单名称")
    code: str = Field(..., description="权限代码")
    description: str | None = Field(description="权限描述")
    menu_type: str = Field(description="菜单类型")
    path: str | None = Field(description="路由路径")
    component: str | None = Field(description="组件路径")
    perms: str | None = Field(description="权限标识")
    icon: str | None = Field(description="图标")
    order_num: int = Field(description="显示顺序")
    visible: bool = Field(description="是否可见")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class PermissionTree(SQLModel):
    """权限树形结构响应模型"""

    id: str = Field(..., description="唯一标识符")
    parent_id: str | None = Field(..., description="父权限ID")
    name: str = Field(..., description="权限/菜单名称")
    code: str = Field(..., description="权限代码")
    menu_type: str = Field(..., description="菜单类型")
    perms: str | None = Field(None, description="权限标识")
    icon: str | None = Field(None, description="图标")
    order_num: int = Field(..., description="显示顺序")
    visible: bool = Field(..., description="是否可见")
    is_active: bool = Field(..., description="是否激活")
    children: list["PermissionTree"] = Field(default_factory=list, description="子权限列表")
