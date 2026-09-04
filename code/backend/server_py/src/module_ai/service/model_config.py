# self
from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelScope,
)
from module_ai.dao.model_config import ModelConfigDao


class ModelConfigService:
    """模型配置服务层"""

    def __init__(self, model_config_dao: ModelConfigDao =None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.model_config_dao = model_config_dao or ModelConfigDao()

    async def _ensure_default_unique(
        self,
        model_type: str,
        current_id: str | None = None,
    ) -> None:
        """
        保证该模型类型的默认公共模型唯一: 若存在旧的默认模型且不是当前记录, 取消其默认标记
        :param model_type: 模型类型
        :param current_id: 当前操作的模型ID(更新时排除自身)
        """
        current = await self.model_config_dao.get_default_by_type(model_type)
        if current is not None and current.id != current_id:
            await self.model_config_dao.update(current.id, ModelConfigUpdate(is_default=False))

    def _normalize_scope(self, model_config: ModelConfigCreate | ModelConfigUpdate) -> None:
        """scope 与 dept_id/is_default 一致性校验与规整"""
        scope = model_config.scope
        # 部门模型必须有归属部门
        if scope == ModelScope.DEPT:
            if not getattr(model_config, "dept_id", None):
                raise ValueError("部门模型必须指定归属部门(dept_id)")
        elif scope is not None:
            # 个人/公共模型不携带部门
            model_config.dept_id = None
        # 默认公共模型标记仅对 public 生效
        if getattr(model_config, "is_default", False) and scope != ModelScope.PUBLIC:
            model_config.dept_id = None

    async def add(self, model_config: ModelConfigCreate) -> str:
        """
        添加新的模型配置(允许同名,以来源/配置区分)
        :param model_config: 模型配置数据
        :return: 创建的模型配置ID
        """
        self._normalize_scope(model_config)
        # 设置默认公共模型时, 先取消该类型旧的默认标记, 保证唯一
        if model_config.scope == ModelScope.PUBLIC and model_config.is_default:
            await self._ensure_default_unique(model_config.model_type.value)
        return await self.model_config_dao.add(model_config)

    async def delete(self, id: str):
        """
        删除模型配置
        :param id: 模型配置ID
        """
        await self.model_config_dao.delete(id)

    async def update(self, model_config_id: str, model_config: ModelConfigUpdate):
        """
        更新模型配置
        :param model_config_id: 模型配置ID
        :param model_config: 更新的模型配置数据
        """
        scope = model_config.scope
        if scope is not None:
            if scope == ModelScope.DEPT and not model_config.dept_id:
                # 更新时若切换为部门但未带部门, 回填当前已存部门
                existing = await self.model_config_dao.get(model_config_id)
                if existing and existing.scope == ModelScope.DEPT:
                    model_config.dept_id = existing.dept_id
                elif existing and not model_config.dept_id:
                    model_config.dept_id = None
            elif scope != ModelScope.DEPT:
                model_config.dept_id = None
        # 默认公共模型唯一性
        if model_config.is_default is True and (
            scope == ModelScope.PUBLIC
            or (scope is None and await self._becomes_public_default(model_config_id))
        ):
            existing = await self.model_config_dao.get(model_config_id)
            if existing:
                await self._ensure_default_unique(model_config.model_type.value, current_id=model_config_id)
        await self.model_config_dao.update(model_config_id, model_config)

    async def _becomes_public_default(self, model_config_id: str) -> bool:
        """更新未显式改 scope 时, 判断是否仍为 public 且当前即为默认"""
        existing = await self.model_config_dao.get(model_config_id)
        if existing is None:
            return False
        return existing.scope == ModelScope.PUBLIC

    async def get(self, id: str) -> ModelConfig | None:
        """
        获取单个模型配置
        :param id: 模型配置ID
        :return: 模型配置对象
        """
        return await self.model_config_dao.get(id)


    async def list_paged(
        self,
        pagination: PaginationParams,
        model: str | None = None,
        model_type: str | None = None,
        server_type: str | None = None,
        user_id: str | None = None,
        dept_id: str | None = None,
        is_admin: bool = False,
        scope: str | None = None,
    ) -> PaginationResponse:
        """
        分页获取模型配置列表(支持多字段过滤 + 当前用户可见性)
        :param pagination: 分页参数
        :param model: 模型标识名称模糊匹配
        :param model_type: 模型类型精确过滤
        :param server_type: 服务类型精确过滤
        :param user_id: 当前用户ID(可见性: 本人模型)
        :param dept_id: 当前用户部门ID(可见性: 部门模型)
        :param is_admin: 管理员可见全部
        :param scope: 归属范围过滤
        :return: 分页响应数据
        """
        items = await self.model_config_dao.list_paged(
            pagination,
            model=model,
            model_type=model_type,
            server_type=server_type,
            user_id=user_id,
            dept_id=dept_id,
            is_admin=is_admin,
            scope=scope,
        )
        total = await self.model_config_dao.count(
            model=model,
            model_type=model_type,
            server_type=server_type,
            user_id=user_id,
            dept_id=dept_id,
            is_admin=is_admin,
            scope=scope,
        )
        return PaginationResponse.create(items, total, pagination)

    async def get_scroll(
        self,
        params: InfiniteScrollParams,
        user_id: str | None = None,
        dept_id: str | None = None,
        is_admin: bool = False,
    ) -> InfiniteScrollResponse:
        """
        滚动加载模型配置列表(带可见性过滤)
        :param params: 滚动参数
        :param user_id/dept_id/is_admin: 见 list_paged
        :return: 滚动响应数据
        """
        items = await self.model_config_dao.get_scroll(
            params, user_id=user_id, dept_id=dept_id, is_admin=is_admin
        )
        return InfiniteScrollResponse.create(items, params.limit)
    
    async def get_default_params(self, model_name: str) -> dict:
        """
        获取指定模型的默认参数kv(基于 ModelConfig 字段默认值)
        :param model_name: 模型标识名称
        :return: 默认参数kv字典
        """
        from pydantic_core import PydanticUndefined

        from module_ai.utils.llm.do.llm_config import ModelConfig

        return {
            name: (info.default if info.default is not PydanticUndefined else None)
            for name, info in ModelConfig.model_fields.items()
            if name != "model"  # model 为调用方传入的标识名称, 不在默认参数内
        }
    

if __name__ == "__main__":
    import asyncio
    from common.config.index import conf
    model_config_service = ModelConfigService()
    async def main():
        model_conf = conf.ai.aliyun.chat_mini
        # 添加一份
        model_obj = ModelConfigCreate(**model_conf.to_dict())
        await model_config_service.add(model_obj)
        pass
    asyncio.run(main())