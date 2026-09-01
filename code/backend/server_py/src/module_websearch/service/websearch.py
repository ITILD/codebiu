from module_websearch.config.settings import DEFAULT_ENGINE, MAX_RESULTS
from module_websearch.utils.websearch.do.websearch import Engine, EngineInfo, SearchResponse
from module_websearch.utils.websearch.factory import ENGINE_CLASSES
from module_websearch.utils.websearch.base import SearchEngine
import logging

logger = logging.getLogger(__name__)


class WebSearchService:
    """网页搜索服务:引擎注册表管理与搜索分发"""

    def __init__(self):
        # 实例化并注册全部引擎(键为引擎唯一标识)
        self._engines: dict[Engine, SearchEngine] = {
            engine_cls.name: engine_cls() for engine_cls in ENGINE_CLASSES
        }

    def get_engine(self, engine: Engine | None) -> SearchEngine:
        """
        按标识获取引擎(为空返回默认引擎)
        :param engine: 引擎标识(duckduckgo/bing)
        :return: 引擎实例
        :raises ValueError: 引擎不存在时抛出
        """
        name = engine or DEFAULT_ENGINE
        engine_instance = self._engines.get(name)
        if not engine_instance:
            available = ", ".join(e.value for e in Engine)
            raise ValueError(f"不支持的搜索引擎: {name}(可选: {available})")
        return engine_instance

    def list_engines(self) -> list[EngineInfo]:
        """列出全部可用引擎元信息(默认引擎排前)"""
        infos = [
            EngineInfo(
                name=engine.name,
                display_name=engine.display_name,
                description=engine.description,
                is_default=engine.name == DEFAULT_ENGINE,
            )
            for engine in self._engines.values()
        ]
        # 默认引擎置顶
        infos.sort(key=lambda info: not info.is_default)
        return infos

    async def search(
        self, query: str, engine: Engine | None = None, limit: int | None = None
    ) -> SearchResponse:
        """
        执行网页搜索
        :param query: 查询词
        :param engine: 引擎标识(为空使用默认引擎 duckduckgo)
        :param limit: 返回条数上限(为空使用模块配置)
        :return: 搜索响应
        """
        query = query.strip()
        if not query:
            raise ValueError("查询词不能为空")
        effective_limit = limit or MAX_RESULTS
        # 条数上限保护(1~30)
        effective_limit = max(1, min(effective_limit, 30))

        engine = self.get_engine(engine)
        results = await engine.search(query, effective_limit)
        logger.info(f"websearch 引擎={engine.name} 关键词={query!r} 命中={len(results)}")
        return SearchResponse(
            query=query,
            engine=engine.name,
            total=len(results),
            results=results,
        )
