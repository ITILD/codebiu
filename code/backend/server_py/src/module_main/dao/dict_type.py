from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_main.do.dict_type import DictType, DictTypeCreate, DictTypeUpdate


class DictTypeDao:
    @DaoRel
    async def add(
        self, dict_type: DictTypeCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增字典类型记录
        :param dict_type: 字典类型创建数据
        :param session: 可选数据库会话
        :return: 新创建字典类型的ID
        """
        db_dict_type = DictType.model_validate(dict_type.model_dump(exclude_unset=True))
        session.add(db_dict_type)
        await session.flush()
        return db_dict_type.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None) -> None:
        """
        删除字典类型记录
        :param id: 要删除的字典类型ID
        :param session: 可选数据库会话
        """
        dict_type = await session.get(DictType, id)
        if not dict_type:
            raise ValueError(f"未找到ID为 {id} 的字典类型")
        await session.delete(dict_type)
        await session.flush()

    @DaoRel
    async def update(
        self,
        dict_type_id: str,
        dict_type: DictTypeUpdate,
        session: AsyncSession | None = None,
    ) -> None:
        """
        直接更新字典类型记录(不先查询)
        :param dict_type_id: 要更新的字典类型ID
        :param dict_type: 字典类型更新数据
        :param session: 可选数据库会话
        :raises: ValueError 如果字典类型不存在
        """
        update_data = dict_type.model_dump(exclude_unset=True)
        stmt = update(DictType).where(DictType.id == dict_type_id).values(**update_data)
        result = await session.exec(stmt)

        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {dict_type_id} 的字典类型")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> DictType | None:
        """
        查询单个字典类型
        :param id: 要查询的字典类型ID
        :param session: 可选数据库会话
        :return: 字典类型对象，未找到返回None
        """
        return await session.get(DictType, id)

    @DaoRel
    async def get_by_code(self, type_code: str, session: AsyncSession | None = None) -> DictType | None:
        """
        根据字典类型编码查询
        :param type_code: 字典类型编码
        :param session: 可选数据库会话
        :return: 字典类型对象，未找到返回None
        """
        statement = select(DictType).where(DictType.type_code == type_code)
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[DictType]:
        """
        分页查询字典类型列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 字典类型列表
        """
        statement = select(DictType).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list[DictType]:
        """
        无限滚动分页查询
        :param params: 无限滚动参数
        :param session: 可选数据库会话
        :return: 字典类型列表
        """
        statement = select(DictType)
        sort_by = params.sort_by if params.sort_by else "created_at"

        if params.last_id:
            last_dict_type = await session.get(DictType, params.last_id)
            if not last_dict_type:
                raise ValueError(f"未找到ID为 {params.last_id} 的字典类型")

            sort_value = getattr(last_dict_type, sort_by)
            search_value = getattr(DictType, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)

        order = None
        if params.direction == ScrollDirection.UP:
            order = getattr(DictType, sort_by).asc()
        else:
            order = getattr(DictType, sort_by).desc()
        statement = statement.order_by(order)
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计字典类型总数
        :param session: 可选数据库会话
        :return: 字典类型总数量
        """
        statement = select(func.count()).select_from(DictType)
        result = await session.exec(statement)
        return result.one()