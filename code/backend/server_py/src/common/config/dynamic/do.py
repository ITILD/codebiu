"""系统动态配置表: 每个配置组一行, value 为该组 Pydantic schema 的 model_dump"""
from datetime import datetime, timezone

from sqlmodel import JSON, Column, DateTime, Field, SQLModel


class SysConfig(SQLModel, table=True):
    __tablename__ = "sys_config"

    group: str = Field(primary_key=True, max_length=50, description="配置组标识(与 yaml 顶层节同名)")
    value: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="配置值(组 schema 的 model_dump)",
    )
    version: int = Field(default=1, description="版本号(每次更新+1)")
    updated_by: str | None = Field(default=None, max_length=64, description="最后更新人(user_id/seed)")
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(timezone.utc),
            nullable=False,
        ),
        description="最后更新时间",
    )
