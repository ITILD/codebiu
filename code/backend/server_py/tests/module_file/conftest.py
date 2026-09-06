"""module_file 测试配置
强制把全局存储替换为临时本地目录(local 实现),保证测试零外部依赖
(无论 config.dev.yaml 的 file_system.storage_type 是 local 还是 s3)。
"""

import shutil

import pytest_asyncio

import module_file.config.filesystem as fs_config
import module_file.service.filesystem as fs_service
from module_file.utils.multi_storage.do.storage_config import (
    StorageConfigFactory,
)
from module_file.utils.multi_storage.storage_factory import StorageFactory


@pytest_asyncio.fixture(scope="session", autouse=True)
async def local_storage_override(tmp_path_factory):
    """session 级: 用临时本地目录替换全局存储单例,测完清理"""
    base_dir = tmp_path_factory.mktemp("file_storage")
    cfg = StorageConfigFactory.create(
        "local", {"max_size": 10, "allowed_extensions": []}
    )
    cfg.base_dir = str(base_dir)
    local_storage = StorageFactory.create(cfg)

    original_storage = fs_config.storage
    original_config = fs_config.storage_config
    fs_config.storage = local_storage
    fs_config.storage_config = cfg
    # service/filesystem.py 通过 from ... import 持有独立引用,同步替换
    fs_service.storage = local_storage
    fs_service.storage_config = cfg
    yield
    fs_config.storage = original_storage
    fs_config.storage_config = original_config
    fs_service.storage = original_storage
    fs_service.storage_config = original_config
    shutil.rmtree(base_dir, ignore_errors=True)
