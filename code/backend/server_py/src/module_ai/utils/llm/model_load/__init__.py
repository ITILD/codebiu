"""模型加载模块

提供统一的模型下载、测试、缓存格式转换能力。

主要导出:
    - ModelDownloader: 模型下载器(ModelScope / HuggingFace 双源)
    - ModelTester: 模型冒烟测试器
    - CacheConverter: 缓存格式转换器(safetensors <-> pytorch 等)
    - JinaReranker / load_qwen_llm / load_embeddings: 模型加载工具
    - ensure_local_model: 兼容旧接口的便捷下载函数
"""
from module_ai.utils.llm.model_load.cache_converter import CacheConverter
from module_ai.utils.llm.model_load.constants import (
    MODELS,
    ModelSpec,
    get_model_spec,
    list_model_keys,
)
from module_ai.utils.llm.model_load.downloader import (
    DownloadSource,
    ModelDownloader,
    ensure_local_model,
)
from module_ai.utils.llm.model_load.loaders import (
    JinaReranker,
    build_chat_prompt,
    cosine_similarity,
    load_embeddings,
    load_qwen_llm,
)
from module_ai.utils.llm.model_load.tester import ModelTester

__all__ = [
    # 下载
    "ModelDownloader",
    "DownloadSource",
    "ensure_local_model",
    # 测试
    "ModelTester",
    # 缓存转换
    "CacheConverter",
    # 加载器
    "JinaReranker",
    "load_qwen_llm",
    "load_embeddings",
    "build_chat_prompt",
    "cosine_similarity",
    # 常量
    "MODELS",
    "ModelSpec",
    "get_model_spec",
    "list_model_keys",
]
