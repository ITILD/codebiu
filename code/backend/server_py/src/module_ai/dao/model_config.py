from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update, or_, and_
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    PaginationParams,
    ScrollDirection,
)
from common.config.db import DaoRel
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelScope,
)


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
        # 准备更新数据(排除未设置的字段)
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
    async def get_default_by_type(
        self, model_type: str, session: AsyncSession | None = None
    ) -> ModelConfig | None:
        """
        获取指定类型的当前默认公共模型(同类型内唯一)
        :param model_type: 模型类型(chat/embeddings/asr/tts等)
        :return: 默认公共模型配置, 未找到返回None
        """
        statement = (
            select(ModelConfig)
            .where(
                ModelConfig.model_type == model_type,
                ModelConfig.scope == ModelScope.PUBLIC,
                ModelConfig.is_default == True,  # noqa: E712
            )
            .limit(1)
        )
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def get_first_by_type(
        self,
        model_type: str,
        session: AsyncSession | None = None,
        server_type: str | None = None,
    ) -> ModelConfig | None:
        """
        获取指定类型的最优先模型配置(语音等工具按类型自动选择方案)
        优先级: 默认公共模型 > 任意公共模型 > 任意配置(回退)
        :param model_type: 模型类型(chat/embeddings/rerank/ocr/asr/tts)
        :param session: 可选数据库会话
        :param server_type: 服务方案精确过滤(可选)
        :return: 模型配置对象, 未找到返回None
        """
        base = select(ModelConfig).where(ModelConfig.model_type == model_type)
        if server_type:
            base = base.where(ModelConfig.server_type == server_type)

        # 1) 优先默认公共模型
        default_stmt = (
            base.where(ModelConfig.scope == ModelScope.PUBLIC, ModelConfig.is_default == True)  # noqa: E712
        ).order_by(ModelConfig.created_at.asc()).limit(1)
        config = (await session.exec(default_stmt)).first()
        if config is not None:
            return config
        # 2) 其次任意公共模型
        public_stmt = (
            base.where(ModelConfig.scope == ModelScope.PUBLIC)
        ).order_by(ModelConfig.created_at.asc()).limit(1)
        config = (await session.exec(public_stmt)).first()
        if config is not None:
            return config
        # 3) 回退: 任意归属配置
        fallback_stmt = base.order_by(ModelConfig.created_at.asc()).limit(1)
        return (await session.exec(fallback_stmt)).first()

    @staticmethod
    def _visibility_condition(
        user_id: str | None,
        dept_id: str | None,
        is_admin: bool = False,
    ):
        """构建可见性条件: 管理员可见全部; 否则 公共/所在部门/本人"""
        if is_admin:
            return None
        conditions = [ModelConfig.scope == ModelScope.PUBLIC]
        if dept_id:
            conditions.append(
                and_(ModelConfig.scope == ModelScope.DEPT, ModelConfig.dept_id == dept_id)
            )
        if user_id:
            conditions.append(
                and_(ModelConfig.scope == ModelScope.USER, ModelConfig.user_id == user_id)
            )
        return or_(ModelConfig.scope == ModelScope.PUBLIC, *conditions[1:]) if conditions else None


    @DaoRel
    async def list_paged(
        self,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
        model: str | None = None,
        model_type: str | None = None,
        server_type: str | None = None,
        user_id: str | None = None,
        dept_id: str | None = None,
        is_admin: bool = False,
        scope: str | None = None,
    ) -> list[ModelConfig]:
        """
        分页获取模型配置列表(支持多字段过滤 + 可见性控制)
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param model: 模型标识名称模糊匹配
        :param model_type: 模型类型精确过滤(chat/embedding/asr/tts等)
        :param server_type: 服务类型精确过滤(openai/dashscope/vllm/ollama/aws)
        :param user_id: 当前用户ID(可见性: 本人模型)
        :param dept_id: 当前用户部门ID(可见性: 所在部门模型)
        :param is_admin: 管理员可见全部
        :param scope: 归属范围过滤(public/dept/user)
        :return: 模型配置列表
        """
        conditions = []
        if model:
            conditions.append(ModelConfig.model.contains(model))
        if model_type:
            conditions.append(ModelConfig.model_type == model_type)
        if server_type:
            conditions.append(ModelConfig.server_type == server_type)
        if scope:
            conditions.append(ModelConfig.scope == scope)

        vis = self._visibility_condition(user_id, dept_id, is_admin)
        if vis is not None:
            conditions.append(vis)

        statement = select(ModelConfig)
        if conditions:
            statement = statement.where(*conditions)
        statement = statement.order_by(ModelConfig.updated_at.desc()).offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(
        self,
        session: AsyncSession | None = None,
        model: str | None = None,
        model_type: str | None = None,
        server_type: str | None = None,
        user_id: str | None = None,
        dept_id: str | None = None,
        is_admin: bool = False,
        scope: str | None = None,
    ) -> int:
        """
        获取模型配置总数(与列表过滤条件保持一致)
        :param session: 可选数据库会话
        :param model: 模型标识名称模糊匹配
        :param model_type: 模型类型精确过滤
        :param server_type: 服务类型精确过滤
        :param user_id/dept_id/is_admin/scope: 同 list_paged
        :return: 模型配置总数
        """
        conditions = []
        if model:
            conditions.append(ModelConfig.model.contains(model))
        if model_type:
            conditions.append(ModelConfig.model_type == model_type)
        if server_type:
            conditions.append(ModelConfig.server_type == server_type)
        if scope:
            conditions.append(ModelConfig.scope == scope)

        vis = self._visibility_condition(user_id, dept_id, is_admin)
        if vis is not None:
            conditions.append(vis)

        statement = select(func.count()).select_from(ModelConfig)
        if conditions:
            statement = statement.where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def get_scroll(
        self,
        params: InfiniteScrollParams,
        session: AsyncSession | None = None,
        user_id: str | None = None,
        dept_id: str | None = None,
        is_admin: bool = False,
    ) -> list:
        """
        滚动加载模型配置列表(带可见性过滤)
        :param params: 滚动参数
        :param session: 可选数据库会话
        :param user_id/dept_id/is_admin: 见 list_paged
        :return: 模型配置列表
        """
        # 返回类型
        statement = select(ModelConfig)
        vis = self._visibility_condition(user_id, dept_id, is_admin)
        if vis is not None:
            statement = statement.where(vis)
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