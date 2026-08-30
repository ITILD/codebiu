from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class RagRole:
    """RAG系统角色常量

    系统级角色(不存储于 project_member 表):
        GUEST: 游客 - 未登录用户，仅可访问公开项目
        SYSTEM_ADMIN: 系统管理员 - 拥有系统全部权限

    项目级角色(存储于 project_member.role):
        PROJECT_ADMIN: 项目管理员 - 项目全部权限(读/写/删/管理成员)
        PROJECT_EDITOR: 项目编辑人员 - 可读/编辑/上传文档
        PROJECT_READER: 项目只读人员 - 仅可读
    """
    # 系统级角色
    GUEST = "guest"
    SYSTEM_ADMIN = "admin"

    # 项目级角色(可分配给 project_member)
    PROJECT_ADMIN = "project_admin"
    PROJECT_EDITOR = "project_editor"
    PROJECT_READER = "project_reader"

    # 项目成员可分配的角色集合
    PROJECT_ROLES = (PROJECT_ADMIN, PROJECT_EDITOR, PROJECT_READER)


class ProjectMemberBase(SQLModel):
    """项目成员基础模型(不含数据库表配置)"""

    user_id: str = Field(..., max_length=50, description="用户ID")
    project_id: str = Field(..., max_length=50, description="项目ID")
    role: str = Field(..., max_length=50, description=f"项目角色({'/'.join(RagRole.PROJECT_ROLES)})")


class ProjectMember(ProjectMemberBase, table=True):
    """项目成员数据库模型(对应数据库表)"""
    __tablename__ = "project_member"
    
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


class ProjectMemberCreate(ProjectMemberBase):
    """创建项目成员的请求模型"""
    pass


class ProjectMemberUpdate(SQLModel):
    """更新项目成员的请求模型"""

    role: str | None = Field(None, max_length=50, description=f"项目角色({'/'.join(RagRole.PROJECT_ROLES)})")


class ProjectMemberResponse(SQLModel):
    """项目成员响应模型"""
    
    id: str = Field(..., description="唯一标识符")
    user_id: str = Field(..., description="用户ID")
    project_id: str = Field(..., description="项目ID")
    role: str = Field(..., description="角色")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")


class MyProjectResponse(SQLModel):
    """我参与的项目响应模型"""
    
    project_id: str = Field(..., description="项目ID")
    project_name: str = Field(..., description="项目名称")
    project_description: str | None = Field(default=None, description="项目描述")
    is_private: bool = Field(default=True, description="是否私有项目")
    kb_category: str = Field(default="project", max_length=20, description="知识库分类(personal/project/company)")
    role: str = Field(..., description="我在项目中的角色")
    created_at: datetime = Field(..., description="项目创建时间")
