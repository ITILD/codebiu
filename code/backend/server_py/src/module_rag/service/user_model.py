from module_rag.do.user_model import UserModel, UserModelUpdate
from module_rag.dao.user_model import UserModelDao
from langchain_core.language_models import BaseChatModel
from module_ai.service.llm_base import LLMBaseService
from module_ai.do.model_config import ModelScope
from module_ai.utils.llm.do.llm_type import ModelType
from module_authorization.config.casbin_rule import auth_manager
from module_authorization.dao.user import UserDao
from common.utils.fastapiEX.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)


class UserModelService:
    """用户-模型绑定服务"""

    def __init__(
        self,
        user_model_dao: UserModelDao | None = None,
        llm_base_service: LLMBaseService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.user_model_dao = user_model_dao or UserModelDao()
        self.llm_base_service = llm_base_service or LLMBaseService()
        self._user_dao = UserDao()  # 查询用户部门以校验部门模型

    async def _validate_model_access(self, model_id: str | None, user_id: str) -> None:
        """
        校验模型配置使用权限: 配置为本人/本部门/公共(is_public)/全局管理员,否则拒绝
        防止用户绑定他人的模型配置(含 api_key)造成越权使用
        :param model_id: 模型配置ID(None 直接放行,表示未绑定)
        :param user_id: 当前用户ID
        :raises ValueError: 配置不存在或无权使用
        """
        if not model_id:
            return
        config = await self.llm_base_service.model_config_service.get(model_id)
        if config is None:
            raise NotFoundError(f"模型配置不存在: {model_id}")
        # 公共模型放行
        if config.scope == ModelScope.PUBLIC:
            return
        # 本人模型放行
        if config.scope == ModelScope.USER and config.user_id == user_id:
            return
        # 部门模型: 校验当前用户所属部门
        if config.scope == ModelScope.DEPT:
            user = await self._user_dao.get(user_id)
            if (
                user is not None
                and user.dept_id
                and config.dept_id
                and user.dept_id == config.dept_id
            ):
                return
        # 全局管理员放行
        enforcer = auth_manager.enforcer
        if enforcer is not None and enforcer.has_grouping_policy(user_id, "admin", "*"):
            return
        raise ValueError(f"无权使用模型配置: {model_id}(仅可用公共/本部门/自己的模型)")

    async def get_by_user(self, user_id: str) -> UserModel | None:
        """
        获取用户的模型绑定
        :param user_id: 用户ID
        :return: 用户-模型绑定对象
        """
        return await self.user_model_dao.get_by_user(user_id)

    async def upsert(self, user_id: str, user_model: UserModelUpdate) -> UserModel:
        """
        新增或更新用户的模型绑定(存在则更新，不存在则创建)
        绑定前校验各模型配置的归属/共享权限
        :param user_id: 用户ID
        :param user_model: 更新数据
        :return: 绑定记录
        :raises ValueError: 任一模型配置不存在或无权使用
        """
        # 绑定校验: 仅校验本次提交的 model_id(未提交字段保持原值不动)
        for model_id in (
            user_model.chat_model_id,
            user_model.embedding_model_id,
            user_model.rerank_model_id,
        ):
            await self._validate_model_access(model_id, user_id)
        existing = await self.user_model_dao.get_by_user(user_id)
        if existing:
            await self.user_model_dao.update_by_user(user_id, user_model)
            return await self.user_model_dao.get_by_user(user_id)
        # 不存在则创建
        create_data = user_model.model_dump(exclude_unset=True)
        new_record = UserModel(user_id=user_id, **create_data)
        await self.user_model_dao.add(new_record)
        # 重新查询以确保返回数据库生成的字段(id/created_at/updated_at)
        return await self.user_model_dao.get_by_user(user_id)

    async def _get_fallback_model_id(self, model_type: ModelType) -> str | None:
        """
        获取回退使用的默认公共模型ID(用户未绑定或绑定失效时使用)
        :param model_type: 模型类型
        :return: 生效的默认公共模型ID, 未找到返回None
        """
        try:
            fallback = await self.llm_base_service.model_config_service.model_config_dao.get_default_by_type(
                model_type.value, active_only=True
            )
            if fallback is not None:
                logger.info(
                    f"用户未绑定/绑定失效 {model_type.value} 模型, 回退使用默认公共模型: "
                    f"{fallback.display_name or fallback.model}"
                )
                return fallback.id
        except Exception as e:
            logger.warning(f"获取默认公共模型回退失败[{model_type.value}]: {e}")
        return None

    async def resolve_model_id(self, user_id: str, model_type: ModelType) -> str | None:
        """解析用户可用的模型ID(绑定→归属校验→默认公共模型回退), 不构建实例;
        供模型存在性预检与实例构建共用
        :param user_id: 用户ID
        :param model_type: 模型类型
        :return: 可用的模型配置ID, 无可用返回None
        """
        model_id: str | None = None
        try:
            binding = await self.get_by_user(user_id)
            if binding is not None:
                match model_type:
                    case ModelType.CHAT:
                        model_id = binding.chat_model_id
                    case ModelType.EMBEDDINGS:
                        model_id = binding.embedding_model_id
                    case ModelType.RERANK:
                        model_id = binding.rerank_model_id
            # 使用时兜底校验(绑定后配置被转手/取消共享的场景)
            await self._validate_model_access(model_id, user_id)
        except ValueError as e:
            logger.warning(f"用户 {user_id} 模型绑定校验失败, 尝试默认公共模型回退: {e}")
            model_id = None
        except Exception as e:
            logger.warning(f"获取用户绑定模型失败, 尝试默认公共模型回退: {e}")
            model_id = None
        # 未绑定/校验失败: 回退默认公共模型
        if not model_id:
            model_id = await self._get_fallback_model_id(model_type)
        return model_id

    async def get_missing_model_types(
        self, user_id: str, model_types: tuple[ModelType, ...] | list[ModelType]
    ) -> list[ModelType]:
        """检查用户可用的模型类型清单(任务派发前预检用)
        :param user_id: 用户ID
        :param model_types: 需要校验的模型类型列表
        :return: 缺失(未绑定且无生效默认公共模型)的类型列表
        """
        missing: list[ModelType] = []
        for model_type in model_types:
            if await self.resolve_model_id(user_id, model_type) is None:
                missing.append(model_type)
        return missing

    async def get_llm_by_user_id(
        self, user_id: str, streaming: bool = True, model_type: ModelType = ModelType.CHAT
    ) -> BaseChatModel | None:
        """根据用户ID获取用户绑定的模型(使用前校验归属/共享权限);
        未绑定或绑定失效时回退到系统默认公共模型(启动 seed 配置)"""
        model_id = await self.resolve_model_id(user_id, model_type)
        if not model_id:
            logger.warning(f"用户 {user_id} 无可用 {model_type.value} 模型(未绑定且无生效的默认公共模型)")
            return None
        try:
            match model_type:
                case ModelType.CHAT:
                    return await self.llm_base_service.get_llm(model_id, streaming=streaming)
                case _:
                    return await self.llm_base_service.get_llm(model_id, False)
        except Exception as e:
            logger.error(f"获取模型实例失败 model_id={model_id}: {e}")
            return None
