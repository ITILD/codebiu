from typing import NamedTuple

from module_rag.do.user_model import UserModel, UserModelUpdate
from module_rag.dao.user_model import UserModelDao
from langchain_core.language_models import BaseChatModel
from module_ai.service.llm import LLMService
from module_ai.do.model_config import ModelScope
from module_ai.utils.llm.types import ModelType
from module_authorization.dao.user import UserDao
from common.utils.fastapiEX.exceptions import NotFoundError
import logging

logger = logging.getLogger(__name__)


class ResolvedModel(NamedTuple):
    """模型解析结果(v4 4.3 兜底链可感知): fallback_used=True 表示绑定失效/未绑定, 已回退默认公共模型"""

    model_id: str | None
    fallback_used: bool = False


class UserModelService:
    """用户-模型绑定服务"""

    def __init__(
        self,
        user_model_dao: UserModelDao | None = None,
        llm_service: LLMService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.user_model_dao = user_model_dao or UserModelDao()
        self.llm_service = llm_service or LLMService()
        self._user_dao = UserDao()  # 查询用户部门以校验部门模型

    async def _validate_model_access(self, model_id: str | None, user_id: str) -> None:
        """
        校验模型配置使用权限: 配置为本人/本部门/公共(is_public),否则拒绝(v4 4.2:
        全局管理员不可绑定使用他人私有模型, 删除 admin 放行)
        防止用户绑定他人的模型配置(含 api_key)造成越权使用
        :param model_id: 模型配置ID(None 直接放行,表示未绑定)
        :param user_id: 当前用户ID
        :raises ValueError: 配置不存在或无权使用
        """
        if not model_id:
            return
        config = await self.llm_service.model_config_service.get(model_id)
        if config is None:
            raise NotFoundError(f"模型配置不存在: {model_id}")
        # 停用模型视为绑定失效(触发回退链, 与前端灰色不可选语义一致)
        if not config.is_active:
            raise ValueError(f"模型配置已停用: {model_id}")
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
        # fallback_disabled 仅接受布尔值: 显式传 null 时过滤掉(其余 None 字段为解绑语义, 保留)
        if user_model.fallback_disabled is None and "fallback_disabled" in user_model.model_fields_set:
            data = user_model.model_dump(exclude_unset=True)
            data.pop("fallback_disabled", None)
            user_model = UserModelUpdate(**data)
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
            fallback = await self.llm_service.model_config_service.model_config_dao.get_default_by_type(
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

    async def _fallback_disabled(self, user_id: str) -> bool:
        """
        读取用户级回退开关(绑定失效时是否禁止回退默认公共模型)
        :param user_id: 用户ID
        :return: True=不回退直接报错; 未配置绑定时默认允许回退
        """
        try:
            binding = await self.user_model_dao.get_by_user(user_id)
            return bool(binding is not None and binding.fallback_disabled)
        except Exception as e:
            logger.warning(f"读取用户 {user_id} 回退开关失败, 按允许回退处理: {e}")
            return False

    async def resolve_model(self, user_id: str, model_type: ModelType) -> ResolvedModel:
        """
        解析用户可用的模型(绑定 → 归属校验 → 回退开关允许时回退默认公共模型), 不构建实例;
        结果标记是否发生回退, 供调用方在响应 meta/SSE 提示数据流向变化(v4 4.3)
        :param user_id: 用户ID
        :param model_type: 模型类型
        :return: ResolvedModel(model_id 为 None 表示无可用模型)
        """
        model_id: str | None = None
        binding_valid = False
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
            binding_valid = model_id is not None
        except ValueError as e:
            logger.warning(f"用户 {user_id} 模型绑定校验失败, 尝试默认公共模型回退: {e}")
            model_id = None
        except Exception as e:
            logger.warning(f"获取用户绑定模型失败, 尝试默认公共模型回退: {e}")
            model_id = None
        if binding_valid:
            return ResolvedModel(model_id=model_id)
        # 绑定失效/未绑定: 用户级开关允许时才回退默认公共模型
        if await self._fallback_disabled(user_id):
            logger.info(f"用户 {user_id} 已关闭模型回退, {model_type.value} 绑定失效不回退")
            return ResolvedModel(model_id=None)
        fallback_id = await self._get_fallback_model_id(model_type)
        return ResolvedModel(model_id=fallback_id, fallback_used=fallback_id is not None)

    async def resolve_model_id(self, user_id: str, model_type: ModelType) -> str | None:
        """解析用户可用的模型ID(resolve_model 的便捷封装, 供模型存在性预检等场景)
        :param user_id: 用户ID
        :param model_type: 模型类型
        :return: 可用的模型配置ID, 无可用返回None
        """
        return (await self.resolve_model(user_id, model_type)).model_id

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
        未绑定或绑定失效时按用户开关回退系统默认公共模型(启动 seed 配置)"""
        resolved = await self.resolve_model(user_id, model_type)
        model_id = resolved.model_id
        if not model_id:
            logger.warning(f"用户 {user_id} 无可用 {model_type.value} 模型(未绑定且无生效的默认公共模型)")
            return None
        if resolved.fallback_used:
            # 兜底链可感知: 数据流向已改变, 记录告警(调用方依据 resolve_model 在响应 meta 提示)
            logger.warning(
                f"用户 {user_id} 的 {model_type.value} 绑定模型不可用, 已回退系统默认公共模型 "
                f"model_id={model_id}(数据将由公共模型处理)"
            )
        try:
            match model_type:
                case ModelType.CHAT:
                    return await self.llm_service.get_llm(model_id, streaming=streaming)
                case _:
                    return await self.llm_service.get_llm(model_id, False)
        except Exception as e:
            logger.error(f"获取模型实例失败 model_id={model_id}: {e}")
            return None
