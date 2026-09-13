import logging

import aiohttp
import requests

from module_ai.utils.llm.rerank.interface import Rerank

logger = logging.getLogger(__name__)

# 重排序接口超时(秒): 检索链路强依赖, 无超时易整体挂起
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


class VllmRerank(Rerank):
    """vLLM /v1/rerank 接口(jina 兼容协议)

    分数范围按模型配置 score_min/score_max 归一化:
        - jina-reranker-v3 原始输出 -0.5~0.5 → 配置 score_min=-0.5, score_max=0.5
        - bge 系经 sigmoid 输出 0~1 → 默认 0~1 即可
    归一化/阈值过滤/top_n 截断统一在基类 arerank_dict_list 实现。
    """

    def __init__(
        self,
        model: str = "/models/jina-reranker-v3",
        base_url: str = "http://192.168.1.252:10002/v1/rerank",
        score_threshold: float | None = None,
        api_key: str | None = None,
        score_min: float = 0.0,
        score_max: float = 1.0,
    ):
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格
        self.score_threshold = score_threshold  # 全局兜底阈值(归一化后 0~1)
        self.api_key = api_key  # 可选: 服务端开启鉴权时携带 Bearer token
        self.score_min = score_min
        self.score_max = score_max

    # 实现基类要求的同步方法
    def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list:
        """同步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return self._result_to_list(result)

    # 实现基类要求的异步方法
    async def arerank(self, query: str, documents: list[str], top_n: int | None = None) -> list:
        """异步文本重排序函数(带超时与状态校验)"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session, session.post(
            self.base_url, headers=headers, json=payload
        ) as response:
            if response.status >= 400:
                body = await response.text()
                raise RuntimeError(
                    f"vLLM 重排序请求失败({response.status}): {body[:500]}"
                )
            result = await response.json()
            return self._result_to_list(result)

    # 内部辅助方法
    def _build_payload_and_headers(self, query: str, documents: list[str], top_n: int | None = None):
        """构建请求的 payload 和 headers(jina 兼容协议: top_n 顶层传)"""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        if top_n:
            payload["top_n"] = top_n

        headers = {"Content-Type": "application/json"}
        # 服务端开启鉴权时携带 Bearer token(api_key 未配置则不加)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return payload, headers

    def _result_to_list(self, result: dict) -> list:
        """将 vLLM 结果转换为列表"""
        return result.get("results", [])
