# self
import asyncio
from datetime import datetime, timezone

from common.utils.db.schema.pagination import InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse
from module_ai.do.model_config import (
    ModelConfig,
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelScope,
)
from module_ai.dao.model_config import ModelConfigDao
from module_ai.utils.llm.types import ModelType
import logging

logger = logging.getLogger(__name__)

# url 协议白名单(v4 4.2 安全要求: 防止私有模型指向内网/任意协议)
_ALLOWED_URL_SCHEMES = ("http://", "https://")


class ModelConfigService:
    """模型配置服务层"""

    def __init__(self, model_config_dao: ModelConfigDao =None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.model_config_dao = model_config_dao or ModelConfigDao()
        # 后台校验任务引用集(防止任务被 GC, 完成后自动移除)
        self._check_tasks: set[asyncio.Task] = set()

    @staticmethod
    def _validate_url(url: str | None) -> None:
        """
        校验 base_url 协议白名单(http/https) + 可选域名黑名单(配置 model_url_domain_blacklist)
        :param url: API基础URL(None/空 跳过)
        :raises ValueError: 协议非法或命中黑名单域名
        """
        if not url:
            return
        lowered = url.strip().lower()
        if not lowered.startswith(_ALLOWED_URL_SCHEMES):
            raise ValueError(f"模型 url 仅支持 http/https 协议: {url}")
        # 可选域名黑名单(走配置节, 未配置则不启用)
        try:
            from common.config.index import conf
            if "model_url_domain_blacklist" in conf:
                blacklist = [str(d).lower() for d in conf.model_url_domain_blacklist]
                if any(d in lowered for d in blacklist if d):
                    raise ValueError(f"模型 url 命中禁用域名: {url}")
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"读取模型 url 域名黑名单配置失败, 跳过校验: {e}")

    @staticmethod
    def _log_write_audit(action: str, config: ModelConfigCreate | ModelConfig | None = None) -> None:
        """模型配置写操作审计日志(logging 起步; 私有/部门模型记录归属与去向)"""
        if config is None:
            return
        scope = getattr(config, "scope", None)
        if scope == ModelScope.PUBLIC:
            return  # 公共模型由管理员维护, 无需逐条审计
        logger.info(
            f"[模型审计] {action} scope={scope} "
            f"model={getattr(config, 'model', None)} "
            f"owner={getattr(config, 'user_id', None)} dept={getattr(config, 'dept_id', None)}"
        )

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
        校验 base_url 协议白名单; 私有/部门模型写操作记审计日志
        :param model_config: 模型配置数据
        :return: 创建的模型配置ID
        """
        self._normalize_scope(model_config)
        self._validate_url(model_config.url)
        # 设置默认公共模型时, 先取消该类型旧的默认标记, 保证唯一
        if model_config.scope == ModelScope.PUBLIC and model_config.is_default:
            await self._ensure_default_unique(model_config.model_type.value)
        model_id = await self.model_config_dao.add(model_config)
        self._log_write_audit("create", model_config)
        # 写库后后台自动校验并回写结果(check_valid/check_format/checked_at)
        self._schedule_check(model_id)
        return model_id

    async def delete(self, id: str):
        """
        删除模型配置
        :param id: 模型配置ID
        """
        existing = await self.model_config_dao.get(id)
        await self.model_config_dao.delete(id)
        self._log_write_audit("delete", existing)

    async def update(self, model_config_id: str, model_config: ModelConfigUpdate):
        """
        更新模型配置
        url/api_key 为空值(None/空串)时跳过更新, 防止前端携带脱敏后的空值覆盖真实密钥;
        校验 base_url 协议白名单; 私有/部门模型写操作记审计日志
        :param model_config_id: 模型配置ID
        :param model_config: 模型配置更新数据
        """
        # 空值保护: 前端编辑被脱敏的模型时 url/api_key 会以空值回传, 不覆盖真实值
        update_data = model_config.model_dump(exclude_unset=True)
        update_data = {
            k: v
            for k, v in update_data.items()
            if not (k in ("url", "api_key") and not v)
        }
        scope = update_data.get("scope") if "scope" in update_data else None
        if scope is not None:
            if scope == ModelScope.DEPT and not update_data.get("dept_id"):
                # 更新时若切换为部门但未带部门, 回填当前已存部门
                existing = await self.model_config_dao.get(model_config_id)
                if existing and existing.scope == ModelScope.DEPT:
                    update_data["dept_id"] = existing.dept_id
                elif existing and not update_data.get("dept_id"):
                    update_data["dept_id"] = None
            elif scope != ModelScope.DEPT:
                update_data["dept_id"] = None
        # 默认公共模型唯一性
        if update_data.get("is_default") is True and (
            scope == ModelScope.PUBLIC
            or ("scope" not in update_data and await self._becomes_public_default(model_config_id))
        ):
            existing = await self.model_config_dao.get(model_config_id)
            if existing:
                # model_type 经 pydantic 校验后为 ModelType 枚举, 统一转 value
                model_type = update_data["model_type"]
                await self._ensure_default_unique(
                    model_type.value if hasattr(model_type, "value") else model_type,
                    current_id=model_config_id,
                )
        if "url" in update_data:
            self._validate_url(update_data["url"])
        if update_data:
            normalized = ModelConfigUpdate(**update_data)
            await self.model_config_dao.update(model_config_id, normalized)
            # 配置变更后重新校验并回写结果
            self._schedule_check(model_config_id)
        # 审计: 以更新后完整记录为准
        self._log_write_audit("update", await self.model_config_dao.get(model_config_id))

    def _schedule_check(self, model_config_id: str) -> None:
        """调度后台连通性校验任务(不阻塞保存接口, 结果回写后前端展示能力标签)"""
        task = asyncio.create_task(self._check_and_persist(model_config_id))
        # 持有任务引用防止被 GC, 完成后自动移除
        self._check_tasks.add(task)
        task.add_done_callback(self._check_tasks.discard)

    async def _check_and_persist(self, model_config_id: str) -> None:
        """后台校验模型配置并把结果回写(check_valid/check_format/checked_at)"""
        try:
            config = await self.model_config_dao.get(model_config_id)
            if config is None:
                return
            # rerank/ocr/asr 等类型暂无自动校验, 结果保持为空
            if config.model_type not in (ModelType.CHAT, ModelType.EMBEDDINGS):
                return
            # 延迟导入避免与 LLMService 循环依赖
            from module_ai.service.llm import LLMService

            result = await LLMService().check_config(config)
            await self.model_config_dao.update(
                model_config_id,
                ModelConfigUpdate(
                    check_valid=result.is_valid,
                    check_format=(
                        result.is_format if config.model_type == ModelType.CHAT else None
                    ),
                    checked_at=datetime.now(timezone.utc),
                ),
            )
            logger.info(
                f"模型配置后台校验完成: {config.model} valid={result.is_valid} format={result.is_format}"
            )
        except Exception as e:
            logger.warning(f"模型配置后台校验失败[{model_config_id}]: {e}")

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
        filter_user_ids: list[str] | None = None,
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
        :param filter_user_ids: 按所有者ID列表过滤(管理员按用户名检索场景)
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
            filter_user_ids=filter_user_ids,
        )
        total = await self.model_config_dao.count(
            model=model,
            model_type=model_type,
            server_type=server_type,
            user_id=user_id,
            dept_id=dept_id,
            is_admin=is_admin,
            scope=scope,
            filter_user_ids=filter_user_ids,
        )
        return PaginationResponse.create(items, total, pagination)

    def mask_secrets(
        self, configs: ModelConfig | list[ModelConfig] | None, user_id: str, is_admin: bool = False
    ) -> None:
        """
        敏感信息脱敏(就地修改): 仅本人私有模型(scope=user 且 user_id==本人)保留 url/api_key 明文,
        公共/部门/他人私有一律脱敏(v4 4.1/4.2: admin 可见全量元数据用于运维, 但密钥除本人私有配置外脱敏)
        :param configs: 单个或多个模型配置对象(None 忽略)
        :param user_id: 当前用户ID
        :param is_admin: 兼容参数(已忽略, v4 后 admin 不再有密钥豁免)
        """
        if configs is None:
            return
        items = configs if isinstance(configs, list) else [configs]
        for config in items:
            if config is None:
                continue
            is_owner_private = (
                config.scope == ModelScope.USER and config.user_id == user_id
            )
            if not is_owner_private:
                config.url = None
                config.api_key = None

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

        from module_ai.utils.llm.factory.config import ModelConfig

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