"""MinerU 引擎配置: 从全局分层配置读取 mineru 节, 缺省回退安全默认值。

配置层级: config.yaml(基线默认值) → config.seed.yaml(密钥) → CODEBIU_* 环境变量,
例如 CODEBIU_MINERU__TOKEN / CODEBIU_MINERU__MODE。
"""
from dataclasses import dataclass

from common.config.index import conf


@dataclass(frozen=True)
class MinerUConfig:
    """MinerU 引擎配置快照(创建解析器时加载一次)。"""

    # 部署模式: remote(mineru.net 远程 API, 默认) / local(本地 docker mineru-api)
    mode: str = "remote"
    # 远程 API token(https://mineru.net 申请)
    token: str = ""
    remote_base_url: str = "https://mineru.net/api/v4"
    # 本地 docker mineru-api 地址; 端点默认为 2.x 契约 /file_parse, 版本差异可调
    local_base_url: str = "http://127.0.0.1:8000"
    local_endpoint: str = "/file_parse"
    # 解析参数
    model_version: str = "pipeline"  # pipeline / vlm
    language: str = "ch"
    is_ocr: bool = False  # False 自动判断是否 OCR
    enable_formula: bool = True
    enable_table: bool = True
    # 网络与轮询(秒)
    timeout: float = 300  # 单次 HTTP 请求超时
    poll_interval: float = 5  # 远程结果轮询间隔
    poll_timeout: float = 1800  # 远程任务最长等待


def load_config() -> MinerUConfig:
    """从全局配置读取 mineru 节构建配置快照; 未配置时全部取安全默认值。"""
    raw = conf.get("mineru", None) or {}

    def _str(key: str, default: str) -> str:
        value = raw.get(key, default)
        return str(value) if value is not None else default

    def _bool(key: str, default: bool) -> bool:
        value = raw.get(key, default)
        return bool(value) if value is not None else default

    def _float(key: str, default: float) -> float:
        value = raw.get(key, default)
        return float(value) if value is not None else default

    return MinerUConfig(
        mode=_str("mode", "remote").strip().lower(),
        token=_str("token", ""),
        remote_base_url=_str("remote_base_url", "https://mineru.net/api/v4").rstrip("/"),
        local_base_url=_str("local_base_url", "http://127.0.0.1:8000").rstrip("/"),
        local_endpoint=_str("local_endpoint", "/file_parse"),
        model_version=_str("model_version", "pipeline"),
        language=_str("language", "ch"),
        is_ocr=_bool("is_ocr", False),
        enable_formula=_bool("enable_formula", True),
        enable_table=_bool("enable_table", True),
        timeout=_float("timeout", 300),
        poll_interval=_float("poll_interval", 5),
        poll_timeout=_float("poll_timeout", 1800),
    )
