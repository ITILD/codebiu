"""全局配置加载: 分层覆盖 + 环境变量键级注入(基线工程配置规范)

层级(低 → 高, 后层覆盖前层):
1. config.yaml            基线层(入 git): 全部配置键的安全默认值 + 注释文档, 开箱即用;
                          默认管理员(admin)归此层(通用引导账户, 非环境敏感)
2. config.seed.yaml       约定种子层(gitignored): 业务配置/模型种子的首启录入来源;
                          存在即加载, 缺失属正常(全新项目直接用基线默认值)
3. state.config_path      基线指向的开发覆盖层(如 config.dev.yaml, 已被 .gitignore);
                          文件缺失时告警跳过(新克隆环境直接用基线默认值启动)
4. CONFIG_PATH 环境变量    部署覆盖层(逗号分隔多文件按序覆盖, 生产/CI 注入);
                          显式指定的文件缺失则启动失败(防止生产静默回退)
5. CODEBIU_* 环境变量      键级覆盖最高优先级(12-factor/容器密钥注入),
                          嵌套键用双下划线: CODEBIU_TOKEN__SECRET_KEY=xxx → token.secret_key

合并语义: 嵌套 dict 深合并(覆盖层只写需要覆盖的键), list 与标量整体替换。
业务配置归动态配置中心: token/email/websearch/file_system/db_cache/db_vector/db_graph/
tasks/admin 九组首启以 yaml 同名节为种子入库, 之后以 系统管理→通用配置页 为准。
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import yaml
from dynaconf import Dynaconf

logger = logging.getLogger(__name__)

# 基线配置文件(相对启动工作目录, 与 dir/temp_source 等相对路径约定一致)
BASE_FILE = Path("config.yaml")
# 约定种子文件(业务配置/模型种子的首启录入来源, gitignored; 存在即加载)
SEED_FILE = Path("config.seed.yaml")
# 部署覆盖层文件环境变量(逗号分隔多个文件, 按序覆盖)
ENV_LAYER_FILES = "CONFIG_PATH"
# 键级环境变量前缀(与 Dynaconf envvar_prefix 一致)
ENV_PREFIX = "CODEBIU"


def _deep_merge(base: dict, overlay: dict) -> dict:
    """递归深合并: 双方均为 dict 时逐键递归, 其余(list/标量)以 overlay 整体覆盖"""
    merged = {**base}
    for key, value in overlay.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_layer(file: Path) -> dict:
    """读取单个 yaml 层(顶层必须为键值映射, 空文件视为空层)"""
    with file.open("r", encoding="utf-8") as fp:
        layer = yaml.safe_load(fp) or {}
    if not isinstance(layer, dict):
        raise ValueError(f"配置文件 {file} 顶层必须是键值映射")
    return layer


def _resolve_layer_files(base: Path = BASE_FILE) -> list[Path]:
    """解析层级文件清单: 基线 → state.config_path → CONFIG_PATH 环境变量

    - state.config_path: 开发便利, 缺失告警跳过(新克隆环境不阻塞)
    - CONFIG_PATH: 部署显式指定, 缺失即失败(防止生产静默回退基线)
    """
    if not base.exists():
        raise FileNotFoundError(f"基线配置文件不存在: {base} (需在 server_py 目录下启动)")
    files = [base]
    # 约定种子层: 存在即加载(缺失属正常, 全新项目用基线默认值)
    if SEED_FILE.exists():
        files.append(SEED_FILE)
    pointer = (_read_layer(base).get("state") or {}).get("config_path")
    if pointer:
        file = Path(pointer)
        if file.exists():
            files.append(file)
        else:
            logger.warning(f"覆盖配置 {pointer} 不存在, 已跳过(仅用基线默认值启动)")
    files.extend(Path(p.strip()) for p in os.getenv(ENV_LAYER_FILES, "").split(",") if p.strip())
    # 部署覆盖层(显式指定, 缺失即失败, 防止生产静默回退基线)
    for file in files[1:]:
        if not file.exists():
            raise FileNotFoundError(f"配置覆盖层文件不存在: {file}")
    return files


def _load_merged(files: list[Path]) -> dict:
    """按序加载全部层并深合并为单 dict(绕开 dynaconf 跨文件按节整体替换的语义)"""
    merged: dict = {}
    for file in files:
        merged = _deep_merge(merged, _read_layer(file))
    return merged


def _build_conf() -> Dynaconf:
    """构建全局配置单例: 深合并结果经 update 注入, 再 execute_loaders 补跑环境变量

    环境变量必须最后执行才能保持最高优先级(update 注入数据的优先级高于 init 期加载)。
    """
    conf = Dynaconf(envvar_prefix=ENV_PREFIX)
    conf.update(_load_merged(_resolve_layer_files()))
    conf.execute_loaders()
    return conf


conf = _build_conf()
# 开发环境标识(影响系统 log\数据库 log 的级别和模式)
is_dev: bool = conf.state.is_dev

if __name__ == "__main__":
    print(conf.state.is_dev)
