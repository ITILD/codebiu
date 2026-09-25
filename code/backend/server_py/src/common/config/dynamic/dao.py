"""sys_config 表 DAO(经 @DaoRel 门面, 每次调用动态解析 session 工厂)"""
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from common.config.db import DaoRel
from common.config.dynamic.do import SysConfig


class SysConfigDao:
    @DaoRel
    async def get(self, group: str, session: AsyncSession | None = None) -> SysConfig | None:
        """按组标识获取配置行, 不存在返回 None"""
        return await session.get(SysConfig, group)

    @DaoRel
    async def list_all(self, session: AsyncSession | None = None) -> list[SysConfig]:
        """获取全部配置行"""
        result = await session.exec(select(SysConfig))
        return list(result.all())

    @DaoRel
    async def upsert(
        self,
        group: str,
        value: dict,
        updated_by: str | None = None,
        session: AsyncSession | None = None,
    ) -> SysConfig:
        """按组写配置(不存在则创建, 存在则覆盖 value 且 version+1)"""
        row = await session.get(SysConfig, group)
        if row is None:
            row = SysConfig(group=group, value=value, updated_by=updated_by)
            session.add(row)
        else:
            row.value = value
            row.version = (row.version or 0) + 1
            row.updated_by = updated_by
        await session.flush()
        return row
