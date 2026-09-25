"""文件存储配置(动态): storage_config 由启动钩子按 sys_config 装配; storage 单例惰性构建保留"""
import logging

from module_file.utils.multi_storage.storage_factory import StorageFactory
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import (
    StorageConfigFactory,
    StorageConfig,
)
from module_file.utils.multi_storage.do.storage_config import StorageType
from common.config.lifespan import register_init_hook
from common.config.path import DIR_UPLOAD

logger = logging.getLogger(__name__)

# 存储配置对象(启动钩子/测试夹具装配; None=未装配)
storage_config: StorageConfig | None = None


async def init_storage_config() -> None:
    """从动态配置装配 storage_config(幂等; lifespan init 钩子与测试夹具调用)"""
    global storage_config
    if storage_config is not None:
        return
    from common.config.dynamic import get_settings
    from common.config.dynamic.schemas import FileSystemSettings

    fs = await get_settings(FileSystemSettings)
    cfg = StorageConfigFactory.create(str(fs.storage_type), fs.model_dump())
    # local 未配置目录时回退到全局上传目录
    if str(fs.storage_type) == StorageType.LOCAL and not getattr(cfg, "base_dir", None):
        cfg.base_dir = str(DIR_UPLOAD)
    storage_config = cfg


@register_init_hook
async def _ensure_storage_config():
    """建表后从动态配置装配存储配置(幂等; 须先于 ensure_storage_ready 等消费钩子)"""
    await init_storage_config()


# 存储实现单例: PEP 562 模块级惰性属性
# `from module_file.config.filesystem import storage` 首次访问时才构建,
# S3 存储时此时才加载 aioboto3 重量级 SDK(避免 import 期占用)
_cached_storage: StorageInterface | None = None


def __getattr__(name: str):
    if name == "storage":
        global _cached_storage
        if _cached_storage is None and storage_config is not None:
            _cached_storage = StorageFactory.create(storage_config)
        return _cached_storage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
