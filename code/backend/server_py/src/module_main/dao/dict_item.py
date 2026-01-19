from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_main.do.dict_item import DictItem, DictItemCreate, DictItemUpdate


class DictItemDao:
    @DaoRel
    async def add(
        self, dict_item: DictItemCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增字典项记录
        :param dict_item: 字典项创建数据
        :param session: 可选数据库会话
        :return: 新创建字典项的ID
        """
        db_dict_item = DictItem.model_validate(dict_item.model_dump(exclude_unset=True))
        session.add(db_dict_item)
        await session.flush()
        return db_dict_item.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None) -> None:
        """
        删除字典项记录
        :param id: 要删除的字典项ID
        :param session: 可选数据库会话
        """
        dict_item = await session.get(DictItem, id)
        if not dict_item:
            raise ValueError(f"未找到ID为 {id} 的字典项")
        await session.delete(dict_item)
        await session.flush()

    @DaoRel
    async def update(
        self,
        dict_item_id: str,
        dict_item: DictItemUpdate,
        session: AsyncSession | None = None,
    ) -> None:
        """
        直接更新字典项记录(不先查询)
        :param dict_item_id: 要更新的字典项ID
        :param dict_item: 字典项更新数据
        :param session: 可选数据库会话
        :raises: ValueError 如果字典项不存在
        """
        update_data = dict_item.model_dump(exclude_unset=True)
        stmt = update(DictItem).where(DictItem.id == dict_item_id).values(**update_data)
        result = await session.exec(stmt)

        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {dict_item_id} 的字典项")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> DictItem | None:
        """
        查询单个字典项
        :param id: 要查询的字典项ID
        :param session: 可选数据库会话
        :return: 字典项对象，未找到返回None
        """
        return await session.get(DictItem, id)

    @DaoRel
    async def get_by_code(self, dict_type_id: str, item_code: str, session: AsyncSession | None = None) -> DictItem | None:
        """
        根据字典类型ID和字典项编码查询
        :param dict_type_id: 字典类型ID
        :param item_code: 字典项编码
        :param session: 可选数据库会话
        :return: 字典项对象，未找到返回None
        """
        statement = select(DictItem).where(
            DictItem.dict_type_id == dict_type_id,
            DictItem.item_code == item_code
        )
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def list_by_dict_type(
        self, dict_type_id: str, session: AsyncSession | None = None
    ) -> list[DictItem]:
        """
        根据字典类型ID查询所有字典项
        :param dict_type_id: 字典类型ID
        :param session: 可选数据库会话
        :return: 字典项列表
        """
        statement = select(DictItem).where(DictItem.dict_type_id == dict_type_id).order_by(DictItem.sort_order)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[DictItem]:
        """
        分页查询字典项列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 字典项列表
        """
        statement = select(DictItem).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list[DictItem]:
        """
        无限滚动分页查询
        :param params: 无限滚动参数
        :param session: 可选数据库会话
        :return: 字典项列表
        """
        statement = select(DictItem)
        sort_by = params.sort_by if params.sort_by else "created_at"

        if params.last_id:
            last_dict_item = await session.get(DictItem, params.last_id)
            if not last_dict_item:
                raise ValueError(f"未找到ID为 {params.last_id} 的字典项")

            sort_value = getattr(last_dict_item, sort_by)
            search_value = getattr(DictItem, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)

        order = None
        if params.direction == ScrollDirection.UP:
            order = getattr(DictItem, sort_by).asc()
        else:
            order = getattr(DictItem, sort_by).desc()
        statement = statement.order_by(order)
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计字典项总数
        :param session: 可选数据库会话
        :return: 字典项总数量
        """
        statement = select(func.count()).select_from(DictItem)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def count_by_dict_type(self, dict_type_id: str, session: AsyncSession | None = None) -> int:
        """
        统计指定字典类型的字典项数量
        :param dict_type_id: 字典类型ID
        :param session: 可选数据库会话
        :return: 字典项数量
        """
        statement = select(func.count()).select_from(DictItem).where(DictItem.dict_type_id == dict_type_id)
        result = await session.exec(statement)
        return result.one()