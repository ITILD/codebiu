from module_ai.utils.llm.rerank.interface import Rerank
import aiohttp
import requests

# 重排序接口超时(秒): 本地服务也可能卡死, 需要兜底超时
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=120)


class OllamaRerank(Rerank):
    """Ollama 风格重排序接口(社区 jina 兼容 shim, 如 bge/Qwen3-Reranker 部署)

    分数范围可通过 score_min/score_max 配置:
        Qwen3-Reranker 经 sigmoid 输出 0~1; 部分部署为原始 logits 或 -0.5~0.5 量纲
    """

    def __init__(
        self,
        model="dengcao/Qwen3-Reranker-0.6B:Q8_0",
        base_url="http://localhost:11434/api/rerank",
        score_min: float = 0.0,
        score_max: float = 1.0,
    ):
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格
        self.score_min = score_min
        self.score_max = score_max

    def _build_payload_and_headers(self, query, documents, top_n=None):
        """构建请求的 payload 和 headers(jina 兼容: top_n 顶层传, parameters 兜底兼容)"""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        if top_n:
            payload["top_n"] = top_n
            payload["parameters"] = {"top_n": top_n}

        headers = {
            "Content-Type": "application/json",
        }
        return payload, headers

    def _result_to_list(self, result) -> list:
        """将结果转换为列表(兼容 {"results": [...]} 与裸列表两种返回形态)"""
        if isinstance(result, dict):
            return result.get("results", [])
        if isinstance(result, list):
            return result
        return []

    def rerank(self, query, documents, top_n=None) -> list:
        """同步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        result = self._result_to_list(result)
        return result

    async def arerank(self, query, documents, top_n=None) -> list:
        """异步文本重排序函数(带超时与状态校验)"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            async with session.post(
                self.base_url, headers=headers, json=payload
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Ollama 重排序请求失败({response.status}): {body[:500]}"
                    )
                result = await response.json()
                return self._result_to_list(result)
