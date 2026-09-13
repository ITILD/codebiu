"""LLM 服务: chat/embeddings 模型的统一调用入口

职责:
    - 按模型配置加载 LangChain 模型实例(构建统一走 utils.llm.factory 工厂, 本服务不重复实现)
    - chat 对话(流式/非流式) 与 embeddings 调用
    - 模型配置连通性/格式化能力校验
    - 模型实例缓存管理(按 配置ID+updated_at+streaming 缓存, 配置变更自动失效旧实例)
"""
import logging
import time
from datetime import datetime, timezone

from langchain.agents import create_agent
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableSequence

from module_ai.do.llm import (
    MODEL_CAPABILITIES,
    ChatRequest,
    ModelCapabilityTestItem,
    ModelChatCheckFormat,
    ModelConfigCheckResponse,
    ModelTestResponse,
)
from module_ai.do.model_config import ModelConfig, ModelConfigCreateRequest
from module_ai.service.model_config import ModelConfigService
from module_ai.utils.llm.factory.builder import build_model
from module_ai.utils.llm.prompts.base import LLMPrompt
from module_ai.utils.llm.rerank.interface import Rerank
from module_ai.utils.llm.types import ModelType

logger = logging.getLogger(__name__)

# 16x16 纯红色 PNG(base64 内嵌, 多模态能力测试用, 避免外网图片依赖; 主流模型要求图片边长>10px)
_VISION_TEST_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP4z8BAEiJN9aiGUQ1DSgMAkPn/Afnh+ngAAAAASUVORK5CYII="
)

# 重排能力测试用例: 语义区分度极大的三级文档(强相关/干扰/明显不相关),
# 用于直观验证排序正确性, 并通过观测分数自动推断模型分数量纲(0~1 或 -0.5~0.5)
_RERANK_TEST_QUERY = "什么是机器学习?"
_RERANK_TEST_DOCS = {
    "relevant": 0,  # 强相关: 应排第一且分数最高
    "noise": 1,     # 干扰项: 含主题词但语义错误, 分数居中
    "irrelevant": 2,  # 明显不相关: 应排最后且分数最低
}
_RERANK_TEST_DOC_TEXTS = [
    "机器学习是人工智能的一个分支，通过算法让计算机从数据中自动学习模式和规律",
    "机器学习是一种用于开发网站的编程语言",
    "今天天气晴朗，适合外出散步和野餐",
]


class LLMService:
    """
    LLM 服务类，提供统一的大语言模型调用接口
    集成模型配置管理、模型工厂构建和基础调用方法
    使用单例模式确保全局唯一实例
    """

    def __init__(
        self,
        model_config_service: ModelConfigService | None = None,
        llm_prompt: LLMPrompt | None = None,
    ):
        """
        初始化LLM服务

        Args:
            model_config_service: 模型配置服务实例，如果不提供则创建默认实例
        """
        self.model_config_service = model_config_service or ModelConfigService()
        self.llm_prompt = llm_prompt or LLMPrompt()
        self._model_cache: dict[str, BaseChatModel | Embeddings | Rerank] = {}

    async def check_config(
        self, model_config_create_request: ModelConfigCreateRequest
    ) -> ModelConfigCheckResponse:
        """校验模型配置连通性与输出格式(创建/修改模型配置时使用, 复用能力测试)

        :param model_config_create_request: 待校验的模型配置
        :return: 校验结果(是否有效/是否支持格式化)
        """
        response = ModelConfigCheckResponse()
        type_key = self._model_type_key(model_config_create_request)
        if type_key not in MODEL_CAPABILITIES:
            logger.error(f"不支持的模型类型: {model_config_create_request.model_type}")
            return response
        try:
            items = await self.run_capability_tests(model_config_create_request)
        except Exception as e:
            logger.warning(f"模型构建失败: {e}")
            return response
        by_cap = {item.capability: item for item in items}
        if type_key == ModelType.CHAT.value:
            response.is_valid = by_cap["chat"].ok
            response.is_format = by_cap["structured"].ok
        elif type_key == ModelType.EMBEDDINGS.value:
            response.is_valid = by_cap["embedding"].ok
        elif type_key == ModelType.RERANK.value:
            response.is_valid = by_cap["rerank"].ok
        return response

    @staticmethod
    def _model_type_key(config) -> str:
        """取模型类型字符串值(兼容枚举/字符串两种形态)"""
        model_type = getattr(config, "model_type", None)
        return model_type.value if hasattr(model_type, "value") else str(model_type)

    async def run_capability_tests(
        self, config, capabilities: list[str] | None = None
    ) -> list[ModelCapabilityTestItem]:
        """按模型类型运行能力测试(未指定时运行该类型全部能力)

        :param config: 模型配置(ModelConfig 或 ModelConfigCreateRequest 均可)
        :param capabilities: 仅运行指定能力(缺省全部)
        :return: 各能力测试结果列表(不支持的类型返回空列表)
        """
        type_key = self._model_type_key(config)
        all_caps = MODEL_CAPABILITIES.get(type_key, [])
        targets = all_caps if not capabilities else [c for c in all_caps if c[0] in set(capabilities)]
        if not targets:
            return []
        # chat/embeddings 类构建实例一次复用(rerank 由测试方法自行构建); 构建失败则全部能力标记失败
        llm = None
        if type_key in (ModelType.CHAT.value, ModelType.EMBEDDINGS.value):
            try:
                llm = build_model(config, streaming=False)
            except Exception as e:
                logger.warning(f"模型构建失败: {e}")
                return [
                    ModelCapabilityTestItem(
                        capability=cap, label=label, ok=False, error=f"模型构建失败: {e}"
                    )
                    for cap, label in targets
                ]
        return [await self._run_capability(cap, label, llm, config) for cap, label in targets]

    async def _run_capability(
        self, capability: str, label: str, llm, config
    ) -> ModelCapabilityTestItem:
        """执行单项能力测试并聚合结果(异常不向上抛, 转为失败项)"""
        start = time.perf_counter()
        ok, detail, error, suggest = False, "", "", None
        try:
            if capability == "chat":
                ok, detail = await self._test_chat(llm)
            elif capability == "structured":
                ok, detail = await self._test_structured(llm)
            elif capability == "vision":
                ok, detail = await self._test_vision(llm)
            elif capability == "embedding":
                ok, detail = await self._test_embedding(llm)
            elif capability == "rerank":
                ok, detail, suggest = await self._test_rerank(config)
        except Exception as e:
            logger.warning(f"能力测试失败 [{capability}]: {e}")
            error = str(e)[:500]
        return ModelCapabilityTestItem(
            capability=capability,
            label=label,
            ok=ok,
            detail=detail,
            error=error,
            elapsed=round(time.perf_counter() - start, 2),
            suggest=suggest,
        )

    async def _test_chat(self, llm) -> tuple[bool, str]:
        """问答能力: 简单算术问答并校验答案包含 2"""
        result = await llm.ainvoke("1+1=? only return result number")
        text = self._content_text(result)
        ok = "2" in text
        return ok, f"回答: {text[:80]}"

    async def _test_structured(self, llm) -> tuple[bool, str]:
        """结构化输出能力: 按 schema(name/age)返回结构化结果并校验"""
        messages = await self.llm_prompt.get_prompt_format_check()
        agent = create_agent(model=llm, response_format=ModelChatCheckFormat)
        result = await agent.ainvoke({"messages": messages})
        fmt = ModelChatCheckFormat.model_validate(result["structured_response"])
        ok = fmt.age == 100
        return ok, f"name={fmt.name} age={fmt.age}"

    async def _test_vision(self, llm) -> tuple[bool, str]:
        """多模态能力: 发送红色方块图片并校验模型能否识别颜色"""
        message = HumanMessage(
            content=[
                {"type": "text", "text": "这张图片中的方块是什么颜色? 只回答中文颜色词"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{_VISION_TEST_IMAGE_B64}"},
                },
            ]
        )
        result = await llm.ainvoke([message])
        text = self._content_text(result)
        ok = any(keyword in text.lower() for keyword in ("红", "red"))
        return ok, f"回答: {text[:80]}"

    async def _test_embedding(self, llm) -> tuple[bool, str]:
        """向量化能力: 嵌入单条文本并校验向量非空"""
        vector = await llm.aembed_query("你好啊")
        dim = len(vector) if vector else 0
        return dim > 0, f"向量维度: {dim}"

    async def _test_rerank(self, config) -> tuple[bool, str, dict | None]:
        """重排能力: 用语义区分度极大的文档验证排序, 并自动推断分数范围

        测试文档刻意选取"强相关 / 干扰 / 明显不相关"三级, 相关文档分数应显著
        高于不相关文档; 同时观测全部原始分数的 min/max, 推断模型真实量纲
        (0~1 或 -0.5~0.5), 与配置的 score_min/score_max 不符时给出建议。
        """
        # 延迟导入避免与 RerankService 循环依赖
        from module_ai.service.rerank import _build_reranker

        reranker = _build_reranker(config)
        ranked = await reranker.arerank(_RERANK_TEST_QUERY, list(_RERANK_TEST_DOC_TEXTS))
        if not ranked:
            return False, "模型未返回任何排序结果", None

        # index -> (原始分, 归一化分)
        score_map = {
            item["index"]: (
                float(item.get("relevance_score", item.get("score", 0.0))),
                reranker.normalize_score(
                    float(item.get("relevance_score", item.get("score", 0.0)))
                ),
            )
            for item in ranked
            if isinstance(item, dict) and item.get("index") is not None
        }
        if len(score_map) < len(_RERANK_TEST_DOCS):
            return False, f"模型返回结果不完整({len(score_map)}/{len(_RERANK_TEST_DOCS)})", None

        # 按归一化分数降序得到文档顺序
        order = sorted(score_map, key=lambda i: score_map[i][1], reverse=True)
        relevant, noise, irrelevant = (
            _RERANK_TEST_DOCS["relevant"],
            _RERANK_TEST_DOCS["noise"],
            _RERANK_TEST_DOCS["irrelevant"],
        )
        # 通过标准: 强相关排第一 且 明显不相关排最后
        ok = order[0] == relevant and order[-1] == irrelevant

        def _fmt(idx: int) -> str:
            raw, norm = score_map[idx]
            return f"{raw:.3f}→{norm:.3f}"

        detail = (
            f"相关({_fmt(relevant)}) > 干扰({_fmt(noise)}) > "
            f"不相关({_fmt(irrelevant)}) [原始分→归一化分]"
        )
        if not ok:
            detail += " | 排序不符合预期, 请检查模型可用性"

        # 自动推断分数范围: 观测原始分数 min/max, 与常用量纲比对给建议
        raw_values = [v[0] for v in score_map.values()]
        observed_min, observed_max = min(raw_values), max(raw_values)
        suggest: dict = {
            "observed_min": round(observed_min, 4),
            "observed_max": round(observed_max, 4),
            "configured_min": reranker.score_min,
            "configured_max": reranker.score_max,
        }
        # 配置范围未覆盖观测分数 → 归一化被 clamp, 阈值过滤会失真
        range_mismatch = (
            observed_min < reranker.score_min - 1e-6
            or observed_max > reranker.score_max + 1e-6
        )
        if range_mismatch:
            suggest["need_fix"] = True
            suggest["score_min"] = observed_min
            suggest["score_max"] = observed_max
            detail += (
                f" | 检测到原始分数范围 [{observed_min:.3f}, {observed_max:.3f}] "
                f"超出配置范围 [{reranker.score_min}, {reranker.score_max}], "
                f"请按建议更新分数范围"
            )
        else:
            suggest["need_fix"] = False
        return ok, detail, suggest

    @staticmethod
    def _content_text(result) -> str:
        """提取模型响应文本(兼容 str/list 形态的 content)"""
        content = getattr(result, "content", "")
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

    async def test_and_persist(
        self, model_id: str, capability: str | None = None
    ) -> ModelTestResponse:
        """按模型ID运行能力测试并把结果回写 check_result(前端能力标签常驻展示)

        :param model_id: 模型配置ID
        :param capability: 仅测试指定能力(缺省测试该类型全部能力)
        :raises ValueError: 模型配置不存在
        """
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            raise ValueError(f"模型配置不存在: {model_id}")
        items = await self.run_capability_tests(config, [capability] if capability else None)
        # 合并回写: 未重测的能力保留历史结果, 已测能力覆盖
        now = datetime.now(timezone.utc)
        merged: dict = dict(config.check_result or {})
        for item in items:
            merged[item.capability] = {
                "capability": item.capability,
                "label": item.label,
                "ok": item.ok,
                "detail": item.detail,
                "error": item.error,
                "elapsed": item.elapsed,
                "checked_at": now.isoformat(),
                "suggest": item.suggest,
            }
        if items:
            await self.model_config_service.persist_check_result(model_id, merged)
        return ModelTestResponse(
            model_id=model_id,
            model_type=self._model_type_key(config),
            capabilities=items,
            checked_at=now,
        )

    async def check_config_by_model_id(self, model_id: str) -> bool:
        """
        校验模型配置是否有效

        Args:
            model_id: 模型配置ID或模型标识名称
        Returns:
            bool: 模型配置是否有效
        """
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            return False
        result = await self.check_config(config)
        return result.is_valid

    async def get_llm(
        self, model_id: str, streaming: bool = True
    ) -> BaseChatModel | Embeddings | Rerank | None:
        """
        按模型配置获取模型实例(带缓存; chat/embeddings/rerank 分别对应
        LangChain 模型与 Rerank 引擎, rerank 实例的分数已按配置量纲归一化)

        Args:
            model_id: 模型配置ID或模型标识名称
            streaming: 是否启用流式响应

        Returns:
            模型实例，配置不存在时返回 None
        """
        # 先获取模型配置, 用 updated_at 参与缓存键, 保证配置变更后自动失效旧实例
        config = await self.model_config_service.get(model_id)
        if not config:
            logger.error(f"模型配置不存在: {model_id}")
            return None
        # 停用模型不可被使用(前端灰色显示, 调用侧同样拦截)
        if not config.is_active:
            logger.warning(f"模型已停用, 拒绝构建实例: {model_id}")
            return None

        # 检查缓存
        cache_key = f"{config.id}_{config.updated_at}_{streaming}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        # 配置已变更: 淘汰该模型旧版本的缓存实例(兼容按 id 或模型名称两种查找方式)
        stale_prefixes = (f"{model_id}_", f"{config.id}_", f"{config.model}_")
        stale_keys = [
            key for key in self._model_cache if key.startswith(stale_prefixes)
        ]
        for key in stale_keys:
            del self._model_cache[key]

        # 经模型工厂构建实例并缓存
        llm_chain = build_model(config, streaming)
        self._model_cache[cache_key] = llm_chain
        return llm_chain

    async def chat_completion(self, request: ChatRequest):
        """聊天完成接口"""
        # 获取LLM处理链
        llm_chain: BaseChatModel = await self.get_llm(request.model_id, streaming=request.streaming)
        if llm_chain is None:
            raise ValueError(f"模型不可用: {request.model_id}")
        # request.messages 是langchain类型
        try:
            # 调用模型
            if request.streaming:
                return llm_chain.astream(request.messages)
            result = await llm_chain.ainvoke(request.messages)
            return result.content
        except Exception as e:
            logger.error(f"模型调用失败: {e}")
            raise

    def clear_cache(self, model_id: str | None = None):
        """
        清除模型缓存

        Args:
            model_id: 模型配置ID，如果为None则清除所有缓存
        """
        if model_id:
            # 清除指定模型的缓存(带 _ 分隔, 防止 id 前缀相近的模型被误清)
            keys_to_remove = [
                key for key in self._model_cache if key.startswith(f"{model_id}_")
            ]
            for key in keys_to_remove:
                del self._model_cache[key]
        else:
            # 清除所有缓存
            self._model_cache.clear()
