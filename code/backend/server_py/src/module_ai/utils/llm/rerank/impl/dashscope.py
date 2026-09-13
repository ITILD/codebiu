from module_ai.utils.llm.rerank.interface import Rerank
import aiohttp
import requests

# 重排序接口超时(秒): 检索链路强依赖, 无超时易整体挂起
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


class DashscopeRerank(Rerank):
    """Dashscope 文本重排序(gte-rerank 系, 输出分数 0~1)

    分数范围可通过 score_min/score_max 覆盖:
        兼容部署在 dashscope 风格接口上的 -0.5~0.5 量纲模型(如 bge-reranker 系)
    """

    def __init__(
        self,
        api_key,
        model="gte-rerank-v2",
        base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
        score_min: float = 0.0,
        score_max: float = 1.0,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格
        self.score_min = score_min
        self.score_max = score_max

    def _build_payload_and_headers(self, query, documents, top_n=None):
        """构建请求的 payload 和 headers"""
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": documents},
        }
        parameters = {}
        if top_n:
            parameters["top_n"] = top_n
        # 根据模型类型设置参数
        if "bge" in self.model:
            payload.update(parameters)
        else:
            # qwen
            parameters["return_documents"] = False  # qwen 不需要返回文档
            payload["parameters"] = parameters
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return payload, headers

    def _result_to_list(self, result) -> list:
        """将结果转换为列表"""
        return result["output"]["results"]

    def rerank(self, query, documents, top_n=None) -> list:
        """同步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        response = requests.post(self.base_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        result = self._result_to_list(result)
        return result

    async def arerank(self, query, documents, top_n=None) -> list:
        """异步文本重排序函数(带超时与状态校验, 错误时抛出响应体便于排查)"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        async with aiohttp.ClientSession(timeout=_REQUEST_TIMEOUT) as session:
            async with session.post(
                self.base_url, headers=headers, json=payload
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise RuntimeError(
                        f"Dashscope 重排序请求失败({response.status}): {body[:500]}"
                    )
                result = await response.json()
                return self._result_to_list(result)


if __name__ == "__main__":
    import asyncio

    async def main():
        query = "什么是机器学习?"
        documents = [
            "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习模式",
            "机器学习是一种编程语言，用于开发网站",
            "机器学习是数据库管理系统的一种",
            "机器学习是操作系统的一种类型",
        ]

        rerank = DashscopeRerank(api_key="YOUR_API_KEY")

        reranked_results = await rerank.arerank(query, documents, 3)
        print("异步重排序结果:")
        print(reranked_results)

        sync_results = rerank.rerank(query, documents, 3)
        print("同步重排序结果:")
        print(sync_results)

    asyncio.run(main())
