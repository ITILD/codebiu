from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update, delete
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_life.do.baby_name import BabyName, BabyNameCreate, BabyNameUpdate, BabyNameBatchDelete


class BabyNameDao:
    @DaoRel
    async def add(
        self, baby_name: BabyNameCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增宝宝名字记录
        :param baby_name: 宝宝名字创建数据
        :param session: 可选数据库会话
        :return: 新创建名字的ID
        """
        db_baby_name = BabyName.model_validate(baby_name.model_dump(exclude_unset=True))
        session.add(db_baby_name)
        await session.flush()
        return db_baby_name.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None) -> str:
        """
        删除宝宝名字记录
        :param id: 要删除的名字ID
        :param session: 可选数据库会话
        """
        baby_name = await session.get(BabyName, id)
        if not baby_name:
            raise ValueError(f"未找到ID为 {id} 的宝宝名字")
        await session.delete(baby_name)
        await session.flush()

    @DaoRel
    async def batch_delete(self, batch_delete: BabyNameBatchDelete, session: AsyncSession | None = None) -> int:
        """
        批量删除宝宝名字记录
        :param batch_delete: 批量删除名字请求模型
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        if not batch_delete.ids:
            return 0
        
        stmt = delete(BabyName).where(BabyName.id.in_(batch_delete.ids))
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount

    @DaoRel
    async def update(self, name_id: str, baby_name: BabyNameUpdate, session: AsyncSession | None = None):
        """
        更新宝宝名字记录
        :param name_id: 要更新的名字ID
        :param baby_name: 更新数据
        :param session: 可选数据库会话
        """
        db_baby_name = await session.get(BabyName, name_id)
        if not db_baby_name:
            raise ValueError(f"未找到ID为 {name_id} 的宝宝名字")
        
        update_data = baby_name.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_baby_name, key, value)
        
        session.add(db_baby_name)
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> BabyName | None:
        """
        获取单个宝宝名字记录
        :param id: 名字ID
        :param session: 可选数据库会话
        :return: 宝宝名字记录或None
        """
        return await session.get(BabyName, id)

    @DaoRel
    async def list_paged(self, pagination: PaginationParams, session: AsyncSession | None = None):
        """
        获取宝宝名字列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 宝宝名字列表
        """
        stmt = select(BabyName).offset(pagination.offset).limit(pagination.limit)

        result = await session.exec(stmt)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        获取宝宝名字总数
        :param session: 可选数据库会话
        :return: 总记录数
        """
        stmt = select(func.count(BabyName.id))
        result = await session.exec(stmt)
        return result.one()

    @DaoRel
    async def get_scroll(self, params: InfiniteScrollParams, session: AsyncSession | None = None):
        """
        滚动加载宝宝名字列表(基于 last_id 游标 + 排序字段)
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 宝宝名字列表(limit+1 条, 由 service 层判断 has_more)
        """
        stmt = select(BabyName)
        # 默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"

        if params.last_id:
            anchor = await session.get(BabyName, params.last_id)
            if not anchor:
                raise ValueError(f"未找到ID为 {params.last_id} 的宝宝名字")

            sort_value = getattr(anchor, sort_by)
            search_value = getattr(BabyName, sort_by)
            if params.direction == ScrollDirection.UP:
                stmt = stmt.where(search_value > sort_value)
            else:
                stmt = stmt.where(search_value < sort_value)

        # 正反排序(查 limit+1 条供 has_more 判断)
        if params.direction == ScrollDirection.UP:
            stmt = stmt.order_by(getattr(BabyName, sort_by).asc())
        else:
            stmt = stmt.order_by(getattr(BabyName, sort_by).desc())
        stmt = stmt.limit(params.limit + 1)

        result = await session.exec(stmt)
        return result.all()