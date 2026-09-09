from common.utils.ai.server.core.rerank import Rerank
import aiohttp
import requests


class DashscopeRerank(Rerank):
    def __init__(
        self,
        api_key,
        model="gte-rerank-v2",
        base_url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格

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
        """异步文本重排序函数"""
        payload, headers = self._build_payload_and_headers(query, documents, top_n)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url, headers=headers, json=payload
            ) as response:
                result = await response.json()
                result = self._result_to_list(result)
                return result


if __name__ == "__main__":
    import asyncio

    async def main():
        from config.index import conf

        API_KEY = conf["ai.vllm_server.reranker.api_key"]

        # query = "红"
        # documents = ["绿", "颜色", "red", "红色"]
        query = "什么是机器学习?"
        documents = [
            "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习模式",
            "机器学习是一种编程语言，用于开发网站",
            "机器学习是数据库管理系统的一种",
            "机器学习是操作系统的一种类型",
        ]

        rerank = DashscopeRerank(API_KEY)

        reranked_results = await rerank.arerank(query, documents, 3)
        print("异步重排序结果:")
        print(reranked_results)

        sync_results = rerank.rerank(query, documents, 3)
        print("同步重排序结果:")
        print(sync_results)

    asyncio.run(main())
