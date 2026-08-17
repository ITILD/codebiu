"""模型加载相关常量配置

集中管理各模型在 HuggingFace / ModelScope 上的仓库 ID 与本地存放路径。
"""
from dataclasses import dataclass
from pathlib import Path

from common.config.path import DIR_MODEL

# 模型根目录 temp_source/model/temp
MODEL_PATH: Path = DIR_MODEL / "temp"


@dataclass(frozen=True)
class ModelSpec:
    """单个模型的下载规格。

    Attributes:
        key: 内部标识，用于从注册表中查找。
        hf_repo_id: HuggingFace 仓库 ID。
        modelscope_id: ModelScope 仓库 ID（国内下载）。
        local_dir: 本地存放目录。
        is_gated: 是否需要 token / 受限访问。
    """

    key: str
    hf_repo_id: str
    modelscope_id: str
    local_dir: Path
    is_gated: bool = False


# =====================
# 预置模型注册表
# =====================
_MODELS: dict[str, ModelSpec] = {
    "qwen_llm": ModelSpec(
        key="qwen_llm",
        hf_repo_id="Qwen/Qwen3.5-0.8B",
        modelscope_id="Qwen/Qwen3.5-0.8B",
        local_dir=MODEL_PATH / "models" / "Qwen3.5-0.8B",
    ),
    "embedding": ModelSpec(
        key="embedding",
        hf_repo_id="jinaai/jina-embeddings-v5-text-small",
        modelscope_id="jinaai/jina-embeddings-v5-text-small",
        local_dir=MODEL_PATH / "models" / "jina-embeddings-v5-text-small",
    ),
    "reranker": ModelSpec(
        key="reranker",
        hf_repo_id="jinaai/jina-reranker-v3",
        modelscope_id="jinaai/jina-reranker-v3",
        local_dir=MODEL_PATH / "models" / "jina-reranker-v3",
    ),
}


def get_model_spec(key: str) -> ModelSpec:
    """根据 key 获取模型规格，不存在则抛出 KeyError。"""
    if key not in _MODELS:
        raise KeyError(f"未注册的模型 key: {key}，可选: {list(_MODELS.keys())}")
    return _MODELS[key]


def list_model_keys() -> list[str]:
    """返回所有已注册模型的 key 列表。"""
    return list(_MODELS.keys())
