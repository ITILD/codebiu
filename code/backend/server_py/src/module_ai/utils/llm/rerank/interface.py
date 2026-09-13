from abc import ABC, abstractmethod

from module_ai.utils.llm.rerank.schemas import RerankResult


class Rerank(ABC):
    """重排序(Rerank)模型抽象接口

    分数范围约定:
        - 不同 rerank 模型输出分数量纲不同(Qwen/gte 为 0~1, jina-v3/bge 部分部署为 -0.5~0.5,
          原始 logits 部署甚至可超出 ±1), 由模型配置 extra.score_min/score_max 声明
        - `arerank` 返回引擎原始分数; `arerank_dict_list` 统一归一化到 0~1 后
          再做 score_threshold 过滤与 top_n 截断, 上游(检索/过滤)只需按 0~1 语义使用
    """

    # 分数范围(子类构造时赋值, 默认 0~1)
    score_min: float = 0.0
    score_max: float = 1.0

    @abstractmethod
    def rerank(self, query: str, texts: list[str], top_n: int | None = None) -> list:
        """同步文本重排序"""

    @abstractmethod
    async def arerank(self, query: str, documents: list[str], top_n: int | None = None) -> list:
        """异步文本重排序(返回引擎原始分数)"""

    def normalize_score(self, raw_score: float) -> float:
        """按配置的分数范围归一化到 [0, 1]

        - 0~1 模型: 原样保留
        - -0.5~0.5 模型: (raw + 0.5) / 1.0 → -0.5→0, 0→0.5, 0.5→1
        - 结果 clamp 到 [0, 1], 防止越界分数污染阈值过滤
        """
        span = self.score_max - self.score_min
        if span <= 0:
            # 非法配置兜底: 视为 0~1 量纲
            return max(0.0, min(1.0, float(raw_score)))
        normalized = (float(raw_score) - self.score_min) / span
        return max(0.0, min(1.0, normalized))

    async def arerank_dict_list(
        self,
        query: str,
        doc_list: list[dict],
        sort_key: str = "content",
        top_n: int | None = None,
        score_threshold: float | None = None,
    ) -> list[RerankResult]:
        """字典列表重排序(统一实现: 归一化 → 阈值过滤 → top_n 截断)

        :param doc_list: 待排序字典列表(保留原始信息映射回 node)
        :param sort_key: 取文本的字段名
        :param top_n: 最终返回条数(None 不过滤)
        :param score_threshold: 归一化后 0~1 的相关性阈值, 低于该值剔除
        :return: [{node, relevance_score(归一化), raw_score(原始), content}] 按分数降序
        """
        if not doc_list:
            return []

        # 1. 提取文本并截断, 防止超长
        document_str_list = [str(doc.get(sort_key, ""))[:4000] for doc in doc_list]

        # 2. 拿全量排序(不向模型传 top_n), 保证阈值过滤在截断前生效
        rerank_results = await self.arerank(
            query=query, documents=document_str_list, top_n=None
        )
        if not rerank_results:
            return []

        # 3. 归一化 + 阈值过滤
        threshold = score_threshold if score_threshold is not None else getattr(self, "score_threshold", None)
        normalized_scores: list[RerankResult] = []
        for item in rerank_results:
            index = item.get("index") if isinstance(item, dict) else None
            if index is None or not (0 <= index < len(doc_list)):
                continue
            raw_score = float(item.get("relevance_score", item.get("score", 0.0)))
            score_value = self.normalize_score(raw_score)
            if threshold is not None and score_value < threshold:
                continue
            original_doc = doc_list[index]
            normalized_scores.append(
                {
                    "node": original_doc.get("node", original_doc),
                    "relevance_score": float(score_value),
                    "raw_score": raw_score,
                    "content": original_doc.get(sort_key, ""),
                }
            )

        # 4. 按归一化分数降序(部分引擎不保证返回有序)后截断 top_n
        normalized_scores.sort(key=lambda x: x["relevance_score"], reverse=True)
        if top_n:
            normalized_scores = normalized_scores[:top_n]
        return normalized_scores
