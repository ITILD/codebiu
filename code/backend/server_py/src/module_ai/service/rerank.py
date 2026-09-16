"""重排序服务: 按模型配置(model_config 表 model_type=rerank)构建引擎并执行重排序

引擎方案由 model_config 表驱动:
    - model_type=rerank + server_type=dashscope/ollama/vllm 的记录即为可选方案
    - model_id 参数可选: 指定时精确匹配, 缺省取该类型最优先配置(默认公共模型优先)
    - 引擎缓存键含配置 updated_at, 配置修改后自动重建
"""
import logging
import time

from common.utils.fastapiEX.exceptions import BusinessError, NotFoundError
from module_ai.dao.model_config import ModelConfigDao
from module_ai.do.model_config import ModelConfig
from module_ai.do.rerank import RerankRequest, RerankResponse
from module_ai.utils.llm.rerank import DashscopeRerank, OllamaRerank, VllmRerank
from module_ai.utils.llm.rerank.interface import Rerank
from module_ai.utils.llm.types import ModelServerType

logger = logging.getLogger(__name__)

# 单文档文本截断上限(超长文档重排序意义有限且耗费 token)
_MAX_DOC_CHARS = 4000


def _build_reranker(config: ModelConfig) -> Rerank:
    """按服务方案构建重排序引擎实例

    :param config: rerank 类型的模型配置
    :raises BusinessError: 服务方案暂未支持
    """
    extra = config.extra or {}
    if config.server_type == ModelServerType.DASHSCOPE:
        return DashscopeRerank(
            api_key=config.api_key,
            model=config.model,
            base_url=config.url
            or "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        )
    if config.server_type == ModelServerType.OLLAMA:
        return OllamaRerank(
            model=config.model,
            base_url=config.url or "http://localhost:11434/api/rerank",
        )
    if config.server_type == ModelServerType.VLLM:
        return VllmRerank(
            model=config.model,
            base_url=config.url or "http://localhost:10002/v1/rerank",
            score_threshold=extra.get("score_threshold"),
        )
    raise BusinessError(f"服务方案 {config.server_type} 暂不支持重排序")


class RerankService:
    """重排序服务: 引擎按模型配置选择(dashscope/ollama/vllm), 实例带缓存"""

    def __init__(self, model_config_dao: ModelConfigDao | None = None):
        """依赖注入构造器: 初始化数据访问对象与引擎缓存"""
        self.model_config_dao = model_config_dao or ModelConfigDao()
        # 引擎缓存: cache_key(id:updated_at) -> 引擎实例(仅保留最新一份, 配置变更后旧实例自动丢弃)
        self._rerankers: dict[str, Rerank] = {}

    async def get_reranker(self, model_id: str | None = None) -> Rerank:
        """获取重排序引擎(指定 model_id 或取 rerank 类型最优先配置)

        :param model_id: 模型配置ID或标识名称(None 时自动选择)
        :raises NotFoundError: 指定的模型配置不存在
        :raises BusinessError: 配置类型不匹配 / 未配置 rerank 模型 / 方案不支持
        """
        if model_id:
            config = await self.model_config_dao.get(model_id)
            if config is None:
                raise NotFoundError(f"模型配置不存在: {model_id}")
            if config.model_type != "rerank":
                raise BusinessError(f"模型配置 {model_id} 不是 rerank 类型")
        else:
            config = await self.model_config_dao.get_first_by_type("rerank")
            if config is None:
                raise BusinessError("未配置 rerank 类型模型, 请先在模型配置中添加")

        # 缓存键含 updated_at: 配置变更自动失效重建
        cache_key = f"{config.id}:{config.updated_at}"
        if cache_key not in self._rerankers:
            self._rerankers = {cache_key: _build_reranker(config)}
            logger.info("重排序引擎已构建: %s/%s", config.server_type, config.model)
        return self._rerankers[cache_key]

    async def rerank(self, request: RerankRequest) -> RerankResponse:
        """执行重排序: 返回按相关性降序的 [{node, relevance_score}] 列表

        :param request: 重排序请求(query + documents)
        :return: 排序结果(node 保留原文档对象)
        """
        start = time.time()
        reranker = await self.get_reranker(request.model_id)

        # 提取待排序文本(字典按 sort_key 取值, 超长截断)
        docs = request.documents
        texts = [
            (doc if isinstance(doc, str) else str(doc.get(request.sort_key, "")))[
                :_MAX_DOC_CHARS
            ]
            for doc in docs
        ]
        if not texts:
            return RerankResponse(results=[], elapsed=round(time.time() - start, 3))

        ranked = await reranker.arerank(request.query, texts, request.top_n)
        # 按返回索引映射回原文档
        results = [
            {
                "node": docs[item["index"]],
                "relevance_score": float(
                    item.get("relevance_score", item.get("score", 0.0))
                ),
            }
            for item in ranked
            if isinstance(item, dict) and item.get("index") is not None
        ]
        return RerankResponse(results=results, elapsed=round(time.time() - start, 3))
