"""一次性清理: 回收 user 角色已下发的 task/geometry 默认策略(声明已置空)"""
import asyncio
import sys

sys.path.insert(0, "src")

from common.config.db import db_manager
from sqlalchemy import text


async def main():
    async with db_manager.db_rel.session_factory() as s:
        rows = (
            await s.execute(
                text("SELECT ptype, v0, v1, v2, v3 FROM casbin_rule WHERE ptype='p' AND v0='user'")
            )
        ).all()
        print("before:", rows)
        result = await s.execute(
            text("DELETE FROM casbin_rule WHERE ptype='p' AND v0='user' AND v1 IN ('task','geometry')")
        )
        await s.commit()
        print("deleted:", result.rowcount)
        rows2 = (
            await s.execute(
                text("SELECT v0, v1, v2, v3 FROM casbin_rule WHERE ptype='p' AND v0='user'")
            )
        ).all()
        print("after:", rows2)


asyncio.run(main())
