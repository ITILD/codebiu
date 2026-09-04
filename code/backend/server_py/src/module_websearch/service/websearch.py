from module_websearch.config.settings import DEFAULT_ENGINE, MAX_RESULTS
from module_websearch.utils.websearch.base import SearchEngine
from module_websearch.utils.websearch.do.websearch import (
    DateRange,
    Engine,
    EngineInfo,
    SearchRequest,
    SearchResponse,
)
from module_websearch.utils.websearch.factory import ENGINE_CLASSES
import logging

logger = logging.getLogger(__name__)


class WebSearchService:
    """网页搜索服务:引擎注册表管理与搜索分发"""

    def __init__(self):
        # 实例化并注册全部引擎(键为引擎唯一标识)
        """依赖注入构造器:初始化所需的数据访问对象"""
        self._engines: dict[Engine, SearchEngine] = {
            engine_cls.name: engine_cls() for engine_cls in ENGINE_CLASSES
        }

    def get_engine(self, engine: Engine | None) -> SearchEngine:
        """
        按标识获取引擎(为空返回默认引擎)
        :param engine: 引擎标识(duckduckgo/tavily/firecrawl)
        :return: 引擎实例
        :raises ValueError: 引擎不存在或未配置(缺 API Key)时抛出
        """
        name = engine or DEFAULT_ENGINE
        engine_instance = self._engines.get(name)
        if not engine_instance:
            available = ", ".join(e.value for e in Engine)
            raise ValueError(f"不支持的搜索引擎: {name}(可选: {available})")
        if not engine_instance.is_configured():
            raise ValueError(f"搜索引擎 {name} 未配置 API Key,请在 config.yaml 的 websearch 段填写")
        return engine_instance

    def list_engines(self) -> list[EngineInfo]:
        """列出全部可用引擎元信息(默认引擎排前)"""
        infos = [
            EngineInfo(
                name=engine.name,
                display_name=engine.display_name,
                description=engine.description,
                is_default=engine.name == DEFAULT_ENGINE,
                requires_api_key=engine.requires_api_key,
                available=engine.is_configured(),
            )
            for engine in self._engines.values()
        ]
        # 默认引擎置顶
        infos.sort(key=lambda info: not info.is_default)
        return infos

    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        执行网页搜索
        :param request: 搜索请求(查询信息/引擎/条数/时间范围/屏蔽站点)
        :return: 搜索响应
        """
        query = request.query.strip()
        if not query:
            raise ValueError("查询信息不能为空")
        effective_limit = request.limit or MAX_RESULTS
        # 条数上限保护(1~30)
        effective_limit = max(1, min(effective_limit, 30))
        date_range = request.date_range or DateRange.ANY

        engine = self.get_engine(request.engine)
        results = await engine.search(query, effective_limit, date_range, request.blocked_sites)
        blocked = SearchEngine.normalize_domains(request.blocked_sites)
        logger.info(
            f"websearch 引擎={engine.name} 关键词={query!r} 时间范围={date_range} "
            f"屏蔽={blocked} 命中={len(results)}"
        )
        return SearchResponse(
            query=query,
            engine=engine.name,
            date_range=date_range,
            blocked_sites=blocked,
            total=len(results),
            results=results,
        )
