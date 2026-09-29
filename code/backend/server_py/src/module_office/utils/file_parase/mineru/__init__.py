"""MinerU 解析引擎。

支持两种部署(配置 mineru.mode):
- remote(默认): mineru.net 远程 API v4, 支持批量解析
- local: 本地 docker 部署的 mineru-api
"""
from module_office.utils.file_parase.mineru.client import BaseMinerUClient, MinerUError, build_client
from module_office.utils.file_parase.mineru.config import MinerUConfig, load_config
from module_office.utils.file_parase.mineru.parser import MinerUParser

__all__ = [
    "MinerUParser",
    "MinerUError",
    "BaseMinerUClient",
    "build_client",
    "MinerUConfig",
    "load_config",
]
