"""
模板字符串数据访问层
"""

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_dev_tools.do.template_string import TemplateString, TemplateStringCreate, TemplateStringUpdate


class TemplateStringDao:
    """
    模板字符串数据访问对象
    """
    
    @DaoRel
    async def add(
        self, template_string: TemplateStringCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增模板字符串记录
        :param template_string: 模板字符串创建数据
        :param session: 可选数据库会话
        :return: 新创建模板字符串的ID
        """
        db_template = TemplateString.model_validate(template_string.model_dump(exclude_unset=True))
        session.add(db_template)
        await session.flush()
        return db_template.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None) -> None:
        """
        删除模板字符串记录
        :param id: 要删除的模板字符串ID
        :param session: 可选数据库会话
        """
        template = await session.get(TemplateString, id)
        if not template:
            raise ValueError(f"未找到ID为 {id} 的模板字符串")
        await session.delete(template)
        await session.flush()

    @DaoRel
    async def update(
        self,
        template_string_id: str,
        template_string: TemplateStringUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        直接更新模板字符串记录
        :param template_string_id: 要更新的模板字符串ID
        :param template_string: 模板字符串更新数据
        :param session: 可选数据库会话
        :return: 更新成功的模板字符串ID
        :raises: ValueError 如果模板字符串不存在
        """
        update_data = template_string.model_dump(exclude_unset=True)
        stmt = update(TemplateString).where(TemplateString.id == template_string_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {template_string_id} 的模板字符串")
        await session.flush()
        return template_string_id

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> TemplateString | None:
        """
        查询单个模板字符串
        :param id: 要查询的模板字符串ID
        :param session: 可选数据库会话
        :return: 模板字符串对象，未找到返回None
        """
        return await session.get(TemplateString, id)

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[TemplateString]:
        """
        分页查询模板字符串列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 模板字符串列表
        """
        statement = select(TemplateString).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list:
        """
        无限滚动分页查询
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 模板字符串列表
        """
        statement = select(TemplateString)
        sort_by = params.sort_by if params.sort_by else "created_at"
        
        if params.last_id:
            last_template = await session.get(TemplateString, params.last_id)
            if not last_template:
                raise ValueError(f"未找到ID为 {params.last_id} 的模板字符串")

            sort_value = getattr(last_template, sort_by)
            search_value = getattr(TemplateString, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)
        
        order = None
        if params.direction == ScrollDirection.UP:
            order = getattr(TemplateString, sort_by).asc()
        else:
            order = getattr(TemplateString, sort_by).desc()
        statement = statement.order_by(order)
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计模板字符串总数
        :param session: 可选数据库会话
        :return: 模板字符串总数量
        """
        statement = select(func.count()).select_from(TemplateString)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def get_by_category(
        self, category: str, session: AsyncSession | None = None
    ) -> list:
        """
        根据分类查询模板字符串
        :param category: 分类名称
        :param session: 可选数据库会话
        :return: 模板字符串列表
        """
        statement = select(TemplateString).where(TemplateString.category == category)
        result = await session.exec(statement)
        return result.all()

