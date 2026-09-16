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
        # 能力测试明细列(JSON, 能力测试接口/后台校验回写)
        if "check_result" not in cols:
            await conn.execute(
                text("ALTER TABLE model_config ADD COLUMN check_result JSON NULL")
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


def _load_default_models_config() -> tuple[bool, dict[str, dict]]:
    """
    从配置文件读取默认公共模型配置(default_models 节)
    :return: (reset_models 总开关, {model_type: 配置dict}); 未配置返回 (False, {})
    :raises: 解析失败时返回 (False, {}), 不抛出
    """
    if "default_models" not in conf or not conf.default_models:
        return False, {}
    raw = conf.default_models
    try:
        # reset_model(reset_models) 为布尔总开关(false=启动不做任何处理); 其余仅接受 dict 类型节
        # (布尔/None 等非法值跳过, 避免一个无效节拖垮整个默认模型 seed)
        reset_models = bool(raw.get("reset_model", raw.get("reset_models", False)))
        sections = {
            str(k).lower(): dict(v)
            for k, v in raw.items()
            if k not in ("reset_model", "reset_models") and isinstance(v, dict)
        }
        return reset_models, sections
    except Exception as e:
        logger.error(f"读取 default_models 配置失败: {e}")
        return False, {}


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


def _config_matches(existing, section: dict) -> bool:
    """判断库中默认公共模型与配置是否一致(仅比较配置中显式写出的模型字段)"""
    return all(
        getattr(existing, k, None) == v
        for k, v in section.items()
        if k in _SEED_ALLOWED_FIELDS
    )


@register_init_hook
async def ensure_voice_server_type():
    """语音模型 server_type 归一化迁移: dashscope->online, sherpa/qwen->local(幂等)

    - 历史方案值写入 extra.legacy_server_type 保留(前端/日志可溯源)
    - 必须先于 ensure_default_models 执行: seed 会比对 server_type, 若旧值未归一化
      会误判"配置不一致"导致旧默认转私有 + 重复建新默认
    """
    if db_manager.db_rel is None:
        return
    import json as _json

    _MIGRATE_MAP = {"dashscope": "online", "sherpa": "local", "qwen": "local"}
    engine = db_manager.db_rel.engine
    async with engine.begin() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT id, server_type, extra FROM model_config "
                    "WHERE model_type IN ('asr', 'tts', 'vad', 'denoise') "
                    "AND server_type IN ('dashscope', 'sherpa', 'qwen')"
                )
            )
        ).fetchall()
        if not rows:
            return
        for row in rows:
            row_id, server_type, extra = row[0], row[1], row[2]
            # extra 可能是 dict(json 列)或 str, 防御性归一
            if isinstance(extra, str):
                try:
                    extra = _json.loads(extra) if extra else {}
                except Exception:
                    extra = {}
            extra = dict(extra or {})
            extra["legacy_server_type"] = server_type
            await conn.execute(
                text("UPDATE model_config SET server_type = :st, extra = CAST(:extra AS JSON) WHERE id = :id"),
                {"st": _MIGRATE_MAP[server_type], "extra": _json.dumps(extra, ensure_ascii=False), "id": row_id},
            )
        logger.info(
            f"语音模型 server_type 已归一化: {len(rows)} 条记录迁移为 online/local"
            f"(原值保留在 extra.legacy_server_type)"
        )


@register_init_hook
async def ensure_default_models():
    """启动时按 config.dev.yaml default_models 补种默认公共模型(幂等, reset_models 总开关控制)

    - reset_models=false(或缺省): 什么都不做, 库中模型配置完全保留
    - reset_models=true 且类型 enabled=true:
      - 库中无该类型默认公共模型: 按配置创建(scope=public/is_default/is_active=True)
      - 已有默认公共模型且与配置一致(配置写出的字段全部相同): 保持不变
      - 不一致(如 model/url/api_key 变更): 原默认模型转为私有(scope=user)保留,
        再按配置创建新的默认公共模型
    - reset_models=true 但类型 enabled=false/未配置: 该类型不做任何处理
    """
    reset_models, seed_config = _load_default_models_config()
    if not reset_models or not seed_config:
        return
    service = ModelConfigService()
    owner_id = await _resolve_seed_owner_id()

    for type_name, section in seed_config.items():
        if not section.get("enabled", False):
            continue
        try:
            model_type = ModelType(type_name)
        except ValueError:
            logger.warning(f"default_models 配置节 '{type_name}' 不是合法模型类型, 已跳过")
            continue
        if not section.get("model"):
            logger.warning(f"default_models 配置节 '{type_name}' 缺少 model 字段, 已跳过")
            continue

        fields = {k: v for k, v in section.items() if k in _SEED_ALLOWED_FIELDS}
        existing = await service.model_config_dao.get_default_by_type(type_name)
        try:
            if existing is None:
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
            elif _config_matches(existing, section):
                logger.info(f"默认公共模型[{type_name}] 与配置一致, 保持不变: {existing.model}")
            else:
                # 与配置不一致: 旧默认转为私有保留(已绑定它的用户回退新默认), 再创建新默认
                await service.model_config_dao.update(
                    existing.id,
                    ModelConfigUpdate(scope=ModelScope.USER, is_default=False),
                )
                create = ModelConfigCreate(
                    **fields,
                    model_type=model_type,
                    scope=ModelScope.PUBLIC,
                    is_default=True,
                    is_active=True,
                    user_id=owner_id,
                )
                await service.add(create)
                logger.info(
                    f"默认公共模型[{type_name}] 配置变更: 原默认已转私有({existing.model}), "
                    f"新默认已创建({create.model})"
                )
        except Exception as e:
            logger.error(f"默认公共模型[{type_name}] seed 失败: {e}")