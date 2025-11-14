import aiohttp
from typing import TypedDict


class RerankRespoenseObj(TypedDict):
    index: int
    relevance_score: float

class RerankResult(TypedDict):
    node: any
    relevance_score: float

class Rerank:
    def __init__(
        self,
        api_key,
        top_n=None,
        model="gte-rerank",
        url="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
    ):
        self.api_key = api_key
        self.top_n = top_n
        self.model = model
        self.url = url

    async def rerank_text(
        self,
        query,
        document_str_list,
    ) -> list[RerankRespoenseObj]:
        """异步文本重排序函数"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": {"query": query, "documents": document_str_list},
        }
        if self.top_n:
            payload["parameters"] = {"top_n": self.top_n}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url, headers=headers, json=payload
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return self._parse_rerank_result(result)
                else:
                    return []

    def _parse_rerank_result(self, result: dict) -> list[RerankRespoenseObj]:
        """解析重排序结果"""
        return result["output"]["results"]

    async def rerank_dict_list(
        self, query, doc_list: list,sort_key="content"
    ) -> list[RerankResult]:
        """异步字典列表重排序函数"""
        if not doc_list:
            return []
        # 提取文本内容列表
        document_str_list = []
   
        for doc in doc_list:
            # 截断超长
            document_str_list.append(doc.get(sort_key,'')[:4000])

        rerank_results: list[RerankRespoenseObj] = await self.rerank_text(
            query, document_str_list
        )
        if not rerank_results:
            return []
        # 根据重排序结果的索引重新排列原始文档
        sorted_documents = []
        for rerank_result in rerank_results:
            sorted_documents.append(
                {
                    "node": doc_list[rerank_result["index"]],
                    "relevance_score": rerank_result["relevance_score"],
                }
            )
        return sorted_documents

    # 多次rerank_dict_list结果合并后排序
    async def sort_all(
        self, all_results: list[RerankResult], top_n=None
    ) -> list[RerankResult]:
        if not all_results:
            return []
        # 按照 relevance_score 降序排序
        sorted_results = sorted(
            all_results, key=lambda x: x["relevance_score"], reverse=True
        )
        # 如果指定了 top_n，返回前 top_n 个结果
        if top_n:
            return sorted_results[:top_n]
        return sorted_results

    # 获取原始节点
    async def get_original_contents(
        self, rerank_results: list[RerankResult]
    ) -> list[str]:
        if not rerank_results:
            return []
        contents = [res["node"] for res in rerank_results if "node" in res]
        return contents


if __name__ == "__main__":
    import asyncio

    # 使用示例
    async def main():
        from config.index import conf

        # 替换为你的 API Key
        API_KEY = conf["ai.openai_server.reranker.api_key"]

        query = "什么是人工智能？"
        documents = [
            {
                "id": 1,
                "content": "机器学习专注于开发算法，使计算机能够从数据中学习和改进。",
            },
            {
                "id": 2,
                "content": "深度学习是机器学习的一个子领域，使用多层神经网络来处理复杂的数据模式。",
            },
            {"id": 3, "content": "计算机视觉致力于使计算机能够解释和理解视觉信息。"},
            {
                "id": 4,
                "content": "人工智能是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。",
            },
        ]

        rerank = Rerank(API_KEY)
        reranked_results = await rerank.rerank_dict_list(query, documents,"content")
        reranked_results = await rerank.sort_all(reranked_results, top_n=3)
        print("重排序结果:")
        print(reranked_results)
        reranked_results = await rerank.get_original_contents(reranked_results)
        print(reranked_results)

    # 运行
    asyncio.run(main())
