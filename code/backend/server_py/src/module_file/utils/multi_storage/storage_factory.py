from module_file.utils.multi_storage.do.storage_config import StorageConfig, LocalStorage, S3Storage
from module_file.utils.multi_storage.session.interface.strorage_interface import StorageInterface


class StorageFactory:
    @staticmethod
    def create(storage_config: StorageConfig) -> StorageInterface:
        """
        根据配置创建指定类型的存储对象

        各实现类延迟导入: aioboto3(S3) 等重量级 SDK 仅在创建对应存储时加载
        """
        if isinstance(storage_config, LocalStorage):
            from module_file.utils.multi_storage.session.impl.storage_local import (
                LocalStorageInterface,
            )

            storage = LocalStorageInterface(storage_config)
        elif isinstance(storage_config, S3Storage):
            from module_file.utils.multi_storage.session.impl.storage_s3 import (
                S3StorageInterface,
            )

            storage = S3StorageInterface(storage_config)
        else:
            raise ValueError(f"Unsupported storage config type: {type(storage_config)}")

        return storage
