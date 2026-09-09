from common.utils.ai.todo.rerank_test.rerank import Rerank
import aiohttp
import requests


class OllamaRerank(Rerank):
    def __init__(
        self,
        model="dengcao/Qwen3-Reranker-0.6B:Q8_0",
        base_url="http://localhost:11434/api/rerank ",
    ):
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格

    def _build_payload_and_headers(self, query, documents, top_n=None):
        """构建请求的 payload 和 headers"""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        if top_n:
            payload["parameters"] = {"top_n": top_n}

        headers = {
            # "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return payload, headers

    def _result_to_list(self, result) -> list:
        """将结果转换为列表"""
        return result

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

        query = "1"
        documents = ["1", "2", "11", "4"]

        rerank = OllamaRerank()

        reranked_results = await rerank.arerank(query, documents, 3)
        print("异步重排序结果:")
        print(reranked_results)

        sync_results = rerank.rerank(query, documents, 3)
        print("同步重排序结果:")
        print(sync_results)

    asyncio.run(main())
