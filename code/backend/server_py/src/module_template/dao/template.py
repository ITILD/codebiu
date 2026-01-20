from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update, delete
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_template.do.template import Template, TemplateCreate, TemplateUpdate, TemplateBatchDelete


class TemplateDao:
    @DaoRel
    async def add(
        self, template: TemplateCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增模板记录
        :param template: 模板创建数据
        :param session: 可选数据库会话
        :return: 新创建模板的ID
        """
        db_template = Template.model_validate(template.model_dump(exclude_unset=True))
        session.add(db_template)
        await session.flush()
        return db_template.id

    # refresh会丢弃本身
    # 是直接refresh还是再次查询自己需要的字段 只要id？
    # refresh(attribute_names=["title"])
    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None) -> str:
        """
        删除模板记录
        :param id: 要删除的模板ID
        :param session: 可选数据库会话
        """
        template = await session.get(Template, id)
        if not template:
            raise ValueError(f"未找到ID为 {id} 的模板")
        await session.delete(template)
        await session.flush()

    @DaoRel
    async def batch_delete(self, batch_delete: TemplateBatchDelete, session: AsyncSession | None = None) -> int:
        """
        批量删除模板记录
        :param batch_delete: 批量删除模板请求模型
        :param session: 可选数据库会话
        :return: 实际删除的记录数
        """
        stmt = delete(Template).where(Template.id.in_(batch_delete.ids))
        result = await session.exec(stmt)
        await session.flush()
        return result.rowcount

    @DaoRel
    async def update(
        self,
        template_id: str,
        template: TemplateUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        直接更新模板记录(不先查询)
        :param template_id: 要更新的模板ID
        :param template: 模板更新数据
        :param session: 可选数据库会话
        :return: 更新成功的模板ID
        :raises: ValueError 如果模板不存在
        """
        # 准备更新数据(排除未设置的字段)
        update_data = template.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(Template).where(Template.id == template_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {template_id} 的模板")
        await session.flush()

    @DaoRel
    async def get(self, id, session: AsyncSession | None = None) -> str:
        """
        查询单个模板
        :param id: 要查询的模板ID
        :param session: 可选数据库会话
        :return: 模板对象，未找到返回None
        """
        return await session.get(Template, id)

    @DaoRel
    async def list_all(
        self, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[Template]:
        """
        分页查询模板列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 模板列表
        """
        statement = select(Template).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def get_scroll(
        self, params: InfiniteScrollParams, session: AsyncSession | None = None
    ) -> list[Template]:
        """
        无限滚动分页查询  先查询最新的 滚下拉更早的
        :param last_id: 最后收到的模板ID(None表示第一页)
        :param limit: 每页最大记录数
        :param session: 可选数据库会话
        :return: 模板列表
        """
        # 返回类型
        statement = select(Template)
        # 设置默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"
        # 根据游标
        if params.last_id:
            last_template = await session.get(Template, params.last_id)
            if not last_template:
                raise ValueError(f"未找到ID为 {params.last_id} 的模板")

            # 获取排序字段的值
            sort_value = getattr(last_template, sort_by)
            search_value = getattr(Template, sort_by)
            condition = None
            if params.direction == ScrollDirection.UP:
                condition = search_value > sort_value
            else:
                condition = search_value < sort_value
            statement = statement.where(condition)
        # 正反排序
        order = None
        if params.direction == ScrollDirection.UP:
            # 升序：从小到大，从早到晚
            order = getattr(Template, sort_by).asc()
        else:
            order = getattr(Template, sort_by).desc()
        statement = statement.order_by(order)
        # 限制结果数量  实际查询 limit + 1 条
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        统计模板总数
        :param session: 可选数据库会话
        :return: 模板总数量
        """
        statement = select(func.count()).select_from(Template)
        result = await session.exec(statement)
        return result.one()
