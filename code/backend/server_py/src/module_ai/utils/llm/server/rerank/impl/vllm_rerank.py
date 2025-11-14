from common.utils.ai.server.core.rerank import Rerank
import aiohttp
import requests

class VllmRerank(Rerank):
    def __init__(
        self,
        model="bge-reranker-v2-m3",
        base_url="http://172.16.25.84:1107/v1/rerank",
    ):
        self.model = model
        self.base_url = base_url.strip()  # 防止 URL 末尾有空格

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

    def _build_payload_and_headers(self, query, documents, top_n=None):
        """构建请求的 payload 和 headers"""
        payload = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        parameters = {}
        if top_n:
            parameters["top_n"] = top_n
        # 根据模型类型设置参数
        if "bge" in self.model:
            payload.update(parameters)
        else:
            # 适配qwen3-reranker-0.6b 效果差
            PREFIX = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
            SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"

            test_instruction = "Given a web search query, retrieve relevant passages that answer the query"
            document_template = "<Document>: {doc}{SUFFIX}"
            # 格式化 Query
            formatted_query = (
                f"{PREFIX}<Instruct>: {test_instruction}\n<Query>: {query}\n"
            )
            # 格式化每个 Document
            formatted_texts = [
                document_template.format(doc=doc, SUFFIX=SUFFIX) for doc in documents
            ]

            payload["query"] = formatted_query
            payload["documents"] = formatted_texts
            # qwen
            parameters["return_documents"] = False  # qwen 不需要返回文档
            payload["additionalProp1"] = parameters
            payload.update(parameters)
        headers = {
            "Content-Type": "application/json",
        }
        return payload, headers

    def _result_to_list(self, result) -> list:
        """将结果转换为列表"""
        return result["results"]


if __name__ == "__main__":
    import asyncio

    async def main():
        from config.index import conf

        query = "红色"
        documents = ["绿", "颜色", "red", "红色"]
        # query = "什么是机器学习？"
        # documents = [ "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习模式", "机器学习是一种编程语言，用于开发网站", "机器学习是数据库管理系统的一种", "机器学习是操作系统的一种类型" ]

        rerank = VllmRerank()

        reranked_results = await rerank.arerank(query, documents, 4)
        print("异步重排序结果:")
        print(reranked_results)

        sync_results = rerank.rerank(query, documents, 4)
        print("同步重排序结果:")
        print(sync_results)

    asyncio.run(main())
