from module_file.utils.multi_storage.storage_factory import StorageFactory
from module_file.utils.multi_storage.session.interface.strorage_interface import (
    StorageInterface,
)
from module_file.utils.multi_storage.do.storage_config import (
    StorageConfigFactory,
    StorageConfig,
)
from common.config.index import conf, is_dev
from common.config.path import DIR_UPLOAD
import logging

logger = logging.getLogger(__name__)
storage: StorageInterface = None
if conf.file_system.storage_type:
    storage_config: StorageConfig = StorageConfigFactory.create(
        conf.file_system.storage_type, conf.file_system
    )
    # 默认使用common配置
    if conf.file_system.storage_type == "local":
        if not conf.file_system.base_dir:
            storage_config.base_dir = str(DIR_UPLOAD)

    storage: StorageInterface = StorageFactory.create(storage_config)
