from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class ProjectMemberBase(SQLModel):
    """项目成员基础模型(不含数据库表配置)"""
    
    user_id: str = Field(..., max_length=50, description="用户ID")
    project_id: str = Field(..., max_length=50, description="项目ID")
    role: str = Field(..., max_length=50, description="角色(admin/member)")


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
    
    role: str | None = Field(None, max_length=50, description="角色(admin/member)")


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
    role: str = Field(..., description="我在项目中的角色")
    created_at: datetime = Field(..., description="项目创建时间")
