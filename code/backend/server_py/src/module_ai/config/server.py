from common.config.server import app
# lib
from common.utils.fastapiEX.exceptions import BizFastAPI
import logging
from sqlalchemy import inspect, text

from common.config.db import db_manager
from common.config.index import conf
from common.config.lifespan import register_init_hook
from module_ai.do.model_config import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelScope,
)
from module_ai.service.model_config import ModelConfigService
from module_ai.utils.llm.types import ModelType

logger = logging.getLogger(__name__)

module_app = BizFastAPI()

app.mount("/ai", module_app)

logger.info("ok...server module_ai服务配置")


@register_init_hook
async def ensure_model_config_scope_columns():
    """存量表补列: model_config 归属范围(scope/dept_id/is_default/display_name)与默认公共模型补全
    (create_all 不为旧表加列,幂等; 兼容旧 is_public 共享标记)"""
    if db_manager.db_rel is None:
        return
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        cols = await conn.run_sync(
            lambda sc: {c["name"] for c in inspect(sc).get_columns("model_config")}
        )
        if "scope" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'user'")
            )
        if "dept_id" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN dept_id VARCHAR(64) NULL")
            )
        if "is_default" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE")
            )
        if "display_name" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN display_name VARCHAR(100) NULL")
            )
        if "is_active" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE")
            )
        # 最近校验结果列(后台自动校验回写, 前端能力标签展示)
        if "check_valid" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN check_valid BOOLEAN NULL")
            )
        if "check_format" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN check_format BOOLEAN NULL")
            )
        if "checked_at" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN checked_at TIMESTAMP WITH TIME ZONE NULL")
            )
        # 枚举列类型统一为 VARCHAR(存量列可能为 PG enum, 与 ORM 的 String 映射不一致会导致
        # "operator does not exist: modeltype = character varying" 比较运算符错误)
        col_types = {
            r[0]: r[1]
            for r in (
                await conn.execute(
                    text(
                        "SELECT column_name, data_type FROM information_schema.columns "
                        "WHERE table_schema = 'public' AND table_name = 'model_config' "
                        "AND column_name IN ('model_type', 'server_type')"
                    )
                )
            ).fetchall()
        }
        for col in ("model_type", "server_type"):
            if col_types.get(col) == "USER-DEFINED":
                await conn.execute(
                    text(f"ALTER TABLE model_config ALTER COLUMN {col} TYPE VARCHAR(30) USING {col}::text")
                )
                logger.info(f"model_config.{col} 已从 PG enum 迁移为 VARCHAR")
        # 遗留 enum 类型清理(列已转 VARCHAR 后不再引用; 失败不影响启动)
        try:
            await conn.execute(text("DROP TYPE IF EXISTS modeltype, modelservertype, modelscope"))
        except Exception as e:
            logger.warning(f"清理遗留 PG enum 类型失败(可忽略): {e}")
        # 旧数据迁移: 存在 is_public 时, is_public=True -> scope=public; False -> scope=user
        if "is_public" in cols:
            await conn.execute(
                text(
                    "UPDATE model_config SET scope = CASE WHEN is_public THEN 'public' ELSE 'user' END "
                    "WHERE scope = 'user' AND is_public = TRUE"
                )
            )
        logger.info("model_config 已补齐 scope/dept_id/is_default/display_name 归属字段")


# ############################# 默认公共模型启动 Seed #############################
# seed 支持的配置字段(ModelConfigCreate 模型字段的白名单, enabled 为开关不属模型字段)
_SEED_ALLOWED_FIELDS = set(ModelConfigCreate.model_fields.keys()) - {"model_type", "scope", "is_default", "is_active", "user_id"}


def _load_default_models_config() -> dict[str, dict]:
    """
    从配置文件读取默认公共模型配置(default_models 节)
    :return: {model_type: 配置dict}; 未配置返回空dict
    """
    if "default_models" not in conf or not conf.default_models:
        return {}
    try:
        # 空节(如 rerank: 后未写内容解析为 None)跳过, 避免一个无效节拖垮整个默认模型 seed
        return {
            str(k).lower(): dict(v)
            for k, v in conf.default_models.items()
            if v is not None
        }
    except Exception as e:
        logger.error(f"读取 default_models 配置失败: {e}")
        return {}


async def _resolve_seed_owner_id() -> str:
    """获取 seed 公共模型的归属用户: 默认管理员账户; 不存在时用 system 占位"""
    from module_authorization.dao.user import UserDao

    username = "admin"
    try:
        username = conf.admin.get("username", "admin") if "admin" in conf else "admin"
        user = await UserDao().get_by_username(username)
        if user is not None:
            return user.id
    except Exception as e:
        logger.warning(f"查询默认管理员 '{username}' 失败, 公共模型归属使用 system 占位: {e}")
    return "system"


@register_init_hook
async def ensure_default_models():
    """启动时按 config.dev.yaml default_models 重置默认公共模型(幂等)

    - enabled=true: 按配置重置该类型公共默认模型(scope=public/is_default/is_active=True)并入库
    - enabled=false 或未配置的类型: 仅将已有公共默认模型标记为不生效(is_active=False), 记录保留,
      管理员可在页面重新配置
    """
    service = ModelConfigService()
    seed_config = _load_default_models_config()
    owner_id = await _resolve_seed_owner_id()

    # 处理类型集合 = 配置节类型 ∪ 库中已有公共默认模型的类型(保证未配置类型被置灰)
    types_in_db = await service.model_config_dao.list_default_public_types()
    model_types = set(seed_config.keys()) | types_in_db
    if not model_types:
        return

    for type_name in model_types:
        section = seed_config.get(type_name)
        if section is None or not section.get("enabled", False):
            # 未配置/未启用: 已有公共默认模型仅标记不生效(记录保留, 前端灰色)
            existing = await service.model_config_dao.get_default_by_type(type_name)
            if existing is not None and existing.is_active:
                await service.model_config_dao.update(
                    existing.id, ModelConfigUpdate(is_active=False)
                )
                logger.info(f"默认公共模型[{type_name}] 未启用配置, 已标记为不生效")
            continue

        # 校验类型合法
        try:
            model_type = ModelType(type_name)
        except ValueError:
            logger.warning(f"default_models 配置节 '{type_name}' 不是合法模型类型, 已跳过")
            continue

        # 按配置过滤出合法字段并构造重置数据
        fields = {k: v for k, v in section.items() if k in _SEED_ALLOWED_FIELDS}
        existing = await service.model_config_dao.get_default_by_type(type_name)
        try:
            if existing is None:
                # 不存在: 创建公共默认模型
                create = ModelConfigCreate(
                    **fields,
                    model_type=model_type,
                    scope=ModelScope.PUBLIC,
                    is_default=True,
                    is_active=True,
                    user_id=owner_id,
                )
                await service.add(create)
                logger.info(f"默认公共模型[{type_name}] 已按配置创建: {create.model}")
            else:
                # 已存在: 按配置重置覆盖(保留记录id, 管理员此前修改的配置被重置)
                update = ModelConfigUpdate(
                    **fields,
                    model_type=model_type,
                    is_default=True,
                    is_active=True,
                )
                # 显式设置的字段才更新, url/api_key 未配置时保持原值
                await service.model_config_dao.update(existing.id, update)
                logger.info(f"默认公共模型[{type_name}] 已按配置重置: {update.model}")
        except Exception as e:
            logger.error(f"默认公共模型[{type_name}] seed 失败: {e}")