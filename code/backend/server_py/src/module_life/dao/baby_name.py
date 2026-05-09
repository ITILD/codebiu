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
    async def list_all(self, pagination: PaginationParams, session: AsyncSession | None = None):
        """
        获取宝宝名字列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 宝宝名字列表
        """
        stmt = select(BabyName).offset(pagination.offset).limit(pagination.limit)
        
        if pagination.order_by:
            order_field = getattr(BabyName, pagination.order_by, None)
            if order_field:
                if pagination.desc:
                    stmt = stmt.order_by(order_field.desc())
                else:
                    stmt = stmt.order_by(order_field.asc())
        
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
        return result.scalar_one()

    @DaoRel
    async def get_scroll(self, params: InfiniteScrollParams, session: AsyncSession | None = None):
        """
        滚动加载宝宝名字列表
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 宝宝名字列表
        """
        stmt = select(BabyName).limit(params.limit)
        
        if params.anchor:
            anchor = await session.get(BabyName, params.anchor)
            if anchor:
                if params.direction == ScrollDirection.UP:
                    stmt = stmt.where(BabyName.id < anchor.id)
                else:
                    stmt = stmt.where(BabyName.id > anchor.id)
        
        if params.order_by:
            order_field = getattr(BabyName, params.order_by, None)
            if order_field:
                if params.desc:
                    stmt = stmt.order_by(order_field.desc())
                else:
                    stmt = stmt.order_by(order_field.asc())
        
        result = await session.exec(stmt)
        return result.all()