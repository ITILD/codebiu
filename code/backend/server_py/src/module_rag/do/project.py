from enum import Enum
from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone


class KbCategory(str, Enum):
    """知识库分类枚举(个人/项目/公司)"""
    PERSONAL = "personal"
    PROJECT = "project"
    COMPANY = "company"

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """返回全部分类值的元组(用于描述文案与校验)"""
        return tuple(member.value for member in cls)


class ProjectBase(SQLModel):
    """项目基础模型(不含数据库表配置)"""

    name: str = Field(..., max_length=100, description="项目名称")
    description: str | None = Field(default=None, max_length=500, description="项目描述")
    is_private: bool = Field(default=True, description="是否私有项目")
    kb_category: str = Field(
        default=KbCategory.PROJECT.value,
        max_length=20,
        description=f"知识库分类({'/'.join(KbCategory.values())})",
    )


class Project(ProjectBase, table=True):
    """项目数据库模型(对应数据库表)"""
    __tablename__ = "project"

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        primary_key=True,
        index=True,
        description="唯一标识符",
    )
    created_by: str = Field(..., max_length=50, description="创建者用户ID")
    root_entry_id: str | None = Field(
        default=None,
        max_length=50,
        index=True,
        description="项目根文件夹条目ID(虚拟目录 /rag/<项目名>/ 的 file_entry id, 惰性补建)",
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


class ProjectCreate(ProjectBase):
    """创建项目的请求模型(客户端只需传 name/description/is_private)"""
    pass


class ProjectUpdate(SQLModel):
    """更新项目的请求模型"""
    
    name: str | None = Field(None, max_length=100, description="项目名称")
    description: str | None = Field(None, max_length=500, description="项目描述")
    is_private: bool | None = Field(None, description="是否私有项目")
    kb_category: str | None = Field(
        None,
        max_length=20,
        description=f"知识库分类({'/'.join(KbCategory.values())})",
    )


class ProjectMyPerms(SQLModel):
    """当前用户对单个知识库的操作权限位(前端按位渲染按钮, 字段命名对齐 v4 5.3)

    内部映射: upload_doc→动作upload(档位>=2), manage_member→invite/remove/manage(档位>=3)
    """

    read: bool = Field(default=False, description="可读(档位>=1)")
    upload_doc: bool = Field(default=False, description="可上传文档(档位>=2)")
    update: bool = Field(default=False, description="可编辑项目信息(档位>=2)")
    delete: bool = Field(default=False, description="可删除项目(档位>=3)")
    manage_member: bool = Field(default=False, description="可管理成员/部门授权/发布(档位>=3)")


class ProjectResponse(SQLModel):
    """项目响应模型"""

    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="项目名称")
    description: str | None = Field(default=None, description="项目描述")
    is_private: bool = Field(default=True, description="是否私有项目")
    kb_category: str = Field(
        default=KbCategory.PROJECT.value,
        max_length=20,
        description=f"知识库分类({'/'.join(KbCategory.values())})",
    )
    created_by: str = Field(..., description="创建者用户ID")
    root_entry_id: str | None = Field(
        default=None, description="项目根文件夹条目ID(虚拟目录 /rag/<项目名>/)"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
    my_perms: ProjectMyPerms | None = Field(
        default=None, description="当前用户操作权限位(列表/详情接口返回; admin 全 True)"
    )
