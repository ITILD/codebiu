from module_file.utils.multi_storage.do.storage_config import StorageConfig, LocalStorage, S3Storage
from module_file.utils.multi_storage.session.interface.strorage_interface import StorageInterface
from module_file.utils.multi_storage.session.impl.storage_local import LocalStorageInterface
from module_file.utils.multi_storage.session.impl.storage_s3 import S3StorageInterface


class StorageFactory:
    @staticmethod
    def create(storage_config: StorageConfig) -> StorageInterface:
        """
        根据配置创建指定类型的存储对象
        """
        if isinstance(storage_config, LocalStorage):
            storage = LocalStorageInterface(storage_config)
        elif isinstance(storage_config, S3Storage):
            storage = S3StorageInterface(storage_config)
        else:
            raise ValueError(f"Unsupported storage config type: {type(storage_config)}")
        
        return storage
