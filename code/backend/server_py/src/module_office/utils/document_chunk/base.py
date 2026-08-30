"""分块器基类与引擎注册中心

采用工程模式设计，支持无缝切换不同分块引擎 (ragflow / langchain)。
每个引擎提供 general / tables / code 策略实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from module_office.utils.document_chunk.do.chunk import (
    ChunkConfig,
    ChunkStrategyEnum,
    ChunkedItem,
)
from module_office.utils.file_parase.do.chunk import Chunk

# 引擎注册表: {engine_name: {strategy_name: chunker_class}}
_CHUNKER_REGISTRY: dict[str, dict[str, type[BaseChunker]]] = {}


class BaseChunker(ABC):
    """分块器基类，定义统一的分块接口"""

    def __init__(self, config: ChunkConfig | None = None):
        self.config = config or ChunkConfig()

    @abstractmethod
    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        """将原始 Chunk 列表按策略重新分块

        :param chunks: 文档解析后的原始分块列表 (保留位置信息)
        :return: 重新分块后的 ChunkedItem 列表
        """
        ...


def register_chunker(engine: str, strategy: str | ChunkStrategyEnum):
    """装饰器: 注册分块器到指定引擎和策略

    用法:
        @register_chunker("ragflow", ChunkStrategyEnum.GENERAL)
        class RAGFlowGeneralChunker(BaseChunker):
            ...
    """
    strategy_value = str(strategy)

    def decorator(cls: type[BaseChunker]) -> type[BaseChunker]:
        if engine not in _CHUNKER_REGISTRY:
            _CHUNKER_REGISTRY[engine] = {}
        _CHUNKER_REGISTRY[engine][strategy_value] = cls
        return cls

    return decorator


def get_chunker(
    engine: str = "ragflow",
    strategy: str | ChunkStrategyEnum = ChunkStrategyEnum.GENERAL,
    config: ChunkConfig | None = None,
) -> BaseChunker:
    """获取分块器实例

    :param engine: 引擎名称 ("ragflow" / "langchain")
    :param strategy: 策略 (ChunkStrategyEnum 或字符串)
    :param config: 分块配置
    :return: 分块器实例
    """
    # 确保引擎模块已加载（触发 @register_chunker 装饰器）
    _ensure_engine_loaded(engine)

    strategy_value = str(strategy)

    engine_map = _CHUNKER_REGISTRY.get(engine)
    if not engine_map:
        raise ValueError(f"未知的分块引擎: {engine}, 已注册: {list(_CHUNKER_REGISTRY.keys())}")

    chunker_cls = engine_map.get(strategy_value) or engine_map.get("general")
    if not chunker_cls:
        raise ValueError(
            f"引擎 {engine} 未注册策略 {strategy_value}, 已注册策略: {list(engine_map.keys())}"
        )
    return chunker_cls(config)


_LOADED_ENGINES: set[str] = set()


def _ensure_engine_loaded(engine: str) -> None:
    """确保引擎模块已导入，触发装饰器注册"""
    if engine in _LOADED_ENGINES:
        return
    if engine == "ragflow":
        from module_office.utils.document_chunk.ragflow import general  # noqa: F401
        from module_office.utils.document_chunk.ragflow import tables  # noqa: F401
        from module_office.utils.document_chunk import code  # noqa: F401
    elif engine == "langchain":
        from module_office.utils.document_chunk.langchain import general  # noqa: F401
        from module_office.utils.document_chunk.langchain import tables  # noqa: F401
        from module_office.utils.document_chunk import code  # noqa: F401
    else:
        raise ValueError(f"未知的分块引擎: {engine}")
    _LOADED_ENGINES.add(engine)
