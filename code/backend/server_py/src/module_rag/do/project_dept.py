from sqlmodel import Column, DateTime, Field, SQLModel
from uuid import uuid4
from datetime import datetime, timezone
from module_rag.do.project_member import RagRole


class ProjectDeptBase(SQLModel):
    """项目部门授权基础模型(不含数据库表配置)"""

    project_id: str = Field(..., max_length=50, description="项目ID")
    dept_id: str = Field(..., max_length=50, description="部门ID(其子部门用户自动继承)")
    role: str = Field(..., max_length=50, description=f"授权档位({'/'.join(RagRole.PROJECT_ROLES)})")


class ProjectDept(ProjectDeptBase, table=True):
    """项目部门授权数据库模型(对应数据库表)

    部门授权是成员表的批量补充: 用户生效档位 = max(直连成员档位, 部门链命中最高档),
    部门链 = 用户所在部门的 ancestors 祖级链 + 自身, 见 dependencies/permission.py
    """
    __tablename__ = "project_dept"

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


class ProjectDeptCreate(ProjectDeptBase):
    """创建部门授权的请求模型"""
    pass


class ProjectDeptUpdate(SQLModel):
    """更新部门授权的请求模型"""

    role: str | None = Field(None, max_length=50, description=f"授权档位({'/'.join(RagRole.PROJECT_ROLES)})")


class ProjectDeptResponse(SQLModel):
    """部门授权响应模型"""

    id: str = Field(..., description="唯一标识符")
    project_id: str = Field(..., description="项目ID")
    dept_id: str = Field(..., description="部门ID")
    role: str = Field(..., description="授权档位")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="最后更新时间")
