from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_ai.do.model_config import ModelConfig, ModelConfigCreate, ModelConfigUpdate


class ModelConfigDao:
    @DaoRel
    async def add(
        self, model_config: ModelConfigCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增模型配置记录
        :param model_config: 模型配置创建数据
        :param session: 可选数据库会话
        :return: 新创建模型配置的ID
        """
        db_model_config = ModelConfig.model_validate(model_config.model_dump(exclude_unset=True))
        session.add(db_model_config)
        await session.flush()
        return db_model_config.id

    @DaoRel
    async def delete(self, id, session: AsyncSession | None = None) -> str:
        """
        删除模型配置记录
        :param id: 要删除的模型配置ID
        :param session: 可选数据库会话
        """
        model_config = await session.get(ModelConfig, id)
        if not model_config:
            raise ValueError(f"未找到ID为 {id} 的模型配置")
        await session.delete(model_config)
        await session.flush()

    @DaoRel
    async def update(
        self,
        model_config_id: str,
        model_config: ModelConfigUpdate,
        session: AsyncSession | None = None,
    ) -> str:
        """
        更新模型配置记录
        :param model_config_id: 模型配置ID
        :param model_config: 模型配置更新数据
        :param session: 可选数据库会话
        """
        # 准备更新数据（排除未设置的字段）
        update_data = model_config.model_dump(exclude_unset=True)

        # 执行直接更新
        stmt = update(ModelConfig).where(ModelConfig.id == model_config_id).values(**update_data)

        result = await session.exec(stmt)

        # 检查是否实际更新了记录
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {model_config_id} 的模板")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> ModelConfig | None:
        """
        获取单个模型配置记录
        :param id: 模型配置ID
        :param session: 可选数据库会话
        :return: 模型配置对象
        """
        return await session.get(ModelConfig, id)


    @DaoRel
    async def list_all(self, pagination: PaginationParams, session: AsyncSession | None = None) -> list[ModelConfig]:
        """
        分页获取模型配置列表
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 模型配置列表
        """
        statement = select(ModelConfig).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(self, session: AsyncSession | None = None) -> int:
        """
        获取模型配置总数
        :param session: 可选数据库会话
        :return: 模型配置总数
        """
        statement = select(func.count()).select_from(ModelConfig)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def get_scroll(self, params: InfiniteScrollParams, session: AsyncSession | None = None) -> list:
        """
        滚动加载模型配置列表
        :param params: 滚动参数
        :param session: 可选数据库会话
        :return: 模型配置列表
        """
        # 返回类型
        statement = select(ModelConfig)
        # 设置默认排序字段为 created_at
        sort_by = params.sort_by if params.sort_by else "created_at"
        # 根据游标
        if params.last_id:
            last_template = await session.get(ModelConfig, params.last_id)
            if not last_template:
                raise ValueError(f"未找到ID为 {params.last_id} 的模板")

            # 获取排序字段的值
            sort_value = getattr(last_template, sort_by)
            search_value = getattr(ModelConfig, sort_by)
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
            order = getattr(ModelConfig, sort_by).asc()
        else:
            order = getattr(ModelConfig, sort_by).desc()
        statement = statement.order_by(order)
        # 限制结果数量  实际查询 limit + 1 条
        statement = statement.limit(params.limit + 1)
        result = await session.exec(statement)
        return result.all()