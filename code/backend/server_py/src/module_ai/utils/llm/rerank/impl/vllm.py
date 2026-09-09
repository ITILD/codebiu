import logging

import aiohttp
import requests

from module_ai.utils.llm.rerank.interface import Rerank
from module_ai.utils.llm.rerank.schemas import RerankResult

logger = logging.getLogger(__name__)

# 具体实现类
class VllmRerank(Rerank):
    def __init__(
        self,
        model: str = "/models/jina-reranker-v3",
        base_url: str = "http://192.168.1.252:10002/v1/rerank",
        score_threshold: float | None = None,
    ):
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格
        self.score_threshold = score_threshold

    def _is_jina_model(self) -> bool:
        """判断是否为 jina-reranker 模型"""
        return "jina" in self.model.lower()

    def _normalize_score(self, score: float) -> float:
        """归一化分数到 [0, 1] 区间。

        jina-reranker-v3 返回分数范围为 [-0.5, 0.5]，归一化到 [0, 1]。
        其他模型原样返回。
        """
        if self._is_jina_model():
            return score + 0.5  # -0.5→0, 0→0.5, 0.5→1
        return score

    # 业务扩展方法：字典列表重排序 (保留原始信息)
    async def arerank_dict_list(
        self, 
        query: str, 
        doc_list: list[dict], 
        sort_key: str = "content", 
        top_n: int | None = None,
        score_threshold: float | None = None  # score阈值

    ) -> list[RerankResult]:
        """
        异步字典列表重排序函数
        """
        if not doc_list:
            return []

        # 1. 提取文本内容列表，并做截断防止超长
        document_str_list = [str(doc.get(sort_key, ""))[:4000] for doc in doc_list]

        logger.info(
            f"[Rerank] 开始重排序 | query='{query[:50]}' | 候选数={len(doc_list)} | "
            f"top_n={top_n} | score_threshold={score_threshold} | 全局threshold={self.score_threshold} | "
            f"模型={self.model} | jina归一化={self._is_jina_model()}"
        )

        # 2. 调用底层的 arerank 获取重排索引和分数
        #    注意: 不向模型传 top_n，先拿回全部候选的完整排序，
        #    再用 score_threshold 过滤，最后才截断 top_n。
        #    这样能保证低分结果在阈值过滤阶段被真正剔除(而非被模型提前截断)。
        rerank_results = await self.arerank(
            query=query,
            documents=document_str_list,
            top_n=None,
        )

        if not rerank_results:
            logger.warning(f"[Rerank] 模型返回空结果 | query='{query[:50]}'")
            return []

        logger.info(
            f"[Rerank] 模型原始返回 {len(rerank_results)} 条 | "
            f"原始分数: {[(r.get('index'), round(r.get('relevance_score', r.get('score', 0.0)), 4)) for r in rerank_results]}"
        )

        # score的最终阈值：优先使用单次传入的，其次使用实例化时的全局配置
        threshold = score_threshold if score_threshold is not None else self.score_threshold

        # 3. 映射回原始字典，并按阈值过滤
        sorted_documents: list[RerankResult] = []
        filtered_count = 0
        for rerank_result in rerank_results:
            original_index = rerank_result.get("index")
            if original_index is None:
                continue

            # 兼容不同 Rerank 模型的返回字段，并归一化分数到 [0, 1]
            raw_score = rerank_result.get("relevance_score", rerank_result.get("score", 0.0))
            score_value = self._normalize_score(float(raw_score))
            # 分数过滤，低于阈值的直接舍弃
            if threshold is not None and score_value < threshold:
                filtered_count += 1
                logger.info(
                    f"[Rerank] 阈值过滤 | index={original_index} raw={round(float(raw_score), 4)} "
                    f"normalized={round(score_value, 4)} < threshold={threshold} → 剔除"
                )
                continue

            if 0 <= original_index < len(doc_list):
                original_doc = doc_list[original_index]
                real_node = original_doc.get("node", original_doc) 
                sorted_documents.append({
                    "node": real_node,
                    "relevance_score": float(score_value),
                    "content": original_doc.get(sort_key, "")     # 保留用于对比的文本
                })

        logger.info(
            f"[Rerank] 阈值过滤完成 | 原始={len(rerank_results)} 过滤掉={filtered_count} 保留={len(sorted_documents)} | "
            f"threshold={threshold}"
        )

        # 4. 阈值过滤后再截断 top_n
        if top_n:
            sorted_documents = sorted_documents[:top_n]
            logger.info(f"[Rerank] top_n 截断 → 最终返回 {len(sorted_documents)} 条 (top_n={top_n})")

        return sorted_documents

    # 实现基类要求的同步方法
    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list:
        """同步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return self._result_to_list(result)

    # 实现基类要求的异步方法
    async def arerank(self, query: str, documents: list[str], top_n: int| None = None) -> list:
        """异步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        async with aiohttp.ClientSession() as session, session.post(
            self.base_url, headers=headers, json=payload
        ) as response:
            response.raise_for_status()
            result = await response.json()
            return self._result_to_list(result)

    # 内部辅助方法
    def _build_payload_and_headers(self, query: str, documents: list[str], top_n: int | None = None):
        """构建请求的 payload 和 headers"""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        parameters = {}
        if top_n:
            parameters["top_n"] = top_n
            
        # 根据模型类型设置参数位置 (兼容 bge 和 jina)
        if "bge" in self.model:
            payload.update(parameters)
        else:
            payload["parameters"] = parameters
            
        headers = {"Content-Type": "application/json"}
        return payload, headers

    def _result_to_list(self, result: dict) -> list:
        """将 vLLM 结果转换为列表"""
        return result.get("results", [])


# ================= 4. 测试用例 =================
if __name__ == "__main__":
    import asyncio

    async def main():
        query = "颜色是哪个？"

        documents_with_metadata = [
            {
                "chunk_id": "c_001",
                "content": "你好",
                "metadata": {"page": 5, "source": "book.pdf"}
            },
            {
                "chunk_id": "c_002",
                "content": "蓝",
                "metadata": {"page": 12, "source": "paper.pdf"}
            },
            {
                "chunk_id": "c_003",
                "content": "绿",
                "metadata": {"page": 8, "source": "book.pdf"}
            },
        ]

        rerank_model = VllmRerank()

        print("开始对字典列表进行 Rerank (保留原始信息)...")
        reranked_results = await rerank_model.arerank_dict_list(
            query=query,
            doc_list=documents_with_metadata,
            sort_key="content",
            top_n=3
        )

        print("\n重排序结果 (包含完整原始 node 和 relevance_score):")
        for res in reranked_results:
            print(f"分数: {res['relevance_score']:.4f} | 原始 chunk_id: {res['node']['chunk_id']} | 内容: {res['node']['content'][:30]}...")

    asyncio.run(main())