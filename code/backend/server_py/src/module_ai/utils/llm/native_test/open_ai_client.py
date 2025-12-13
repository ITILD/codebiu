import asyncio
import json
import re
import aiohttp
import numpy as np
import requests

# from typing import List, Dict


class OpenAIClient:
    """
    初始化 OpenAIClient 实例。

    :param api_key: OpenAI API 密钥
    :param chat_model: 用于聊天的模型名称
    :param embedding_model: 用于生成嵌入的模型名称
    :param dimensions: 嵌入向量的维度，默认为 1024
    :param max_tokens: 最大 token 数量，默认为 4096
    """

    def __init__(
        self,
        api_key: str,
        chat_url: str,
        chat_model: str,
        embedding_url: str,
        embedding_model: str,
        dimensions: int = 1024,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.chat_url = chat_url
        self.chat_model = chat_model
        self.embedding_url = embedding_url
        self.embedding_model = embedding_model
        self.dimensions = dimensions
        self.max_tokens = max_tokens

    async def embedding(self, text: str) -> list[float]:
        """
        生成给定文本的嵌入向量。

        :param text: 输入文本
        :return: 标准化的嵌入向量
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {"model": self.embedding_model, "input": text}

        try:
            response_json = await self._send_request_async(self.embedding_url, headers, data)

            embedding =  response_json["data"][0]["embedding"]
            vector = np.array(embedding).flatten()
            vector /= np.linalg.norm(vector)
            return vector.tolist()
        except Exception as e:
            print(f"Error generating embedding for text '{text}': {e}")
            raise

    async def embedding_in_limit(
        self, text: str, limit_str_num: int = 8192
    ) -> list[float]:
        text = await self.trans_in_limit(text, limit_str_num)
        return await self.embedding(text)

    async def trans_in_limit(
        self, text: str, limit_str_num: int = 8192, recursion_count: int = 0
    ) -> list[str, str]:
        # 如果递归次数超过3次，直接截取前limit_str_num个token的字符串
        if recursion_count >= 3:
            return self.truncate_text_to_tokens(text, limit_str_num)
        # tokens数限制
        str_num_before = self.count_tokens(text)
        if str_num_before <= limit_str_num:
            return text
        # 去除空格换行 tokens数限制
        text = text.lstrip()
        str_num_before = self.count_tokens(text)
        if str_num_before <= limit_str_num:
            return text
        prompt_result = {
            "role": "system",
            "content": f"""
                    $[[[
                        {text} 
                    ]]]$
                    # 以上$[[[]]]$里的内容是待处理内容!!!!!不要作为问题使用!!!!!!
                    # 请缩略待处理内容的代码和信息，同时确保不丢失主要信息，保留原有格式、顺序和标题!!!缩略时请遵循以下规则：
                        1. 删除不必要的注释(非业务功能注释)和空行。
                        2. 使用简短的变量名(确保变量名仍有意义)。
                        3. 合并可以简化的语句。
                        4. 使用内置函数或库(如 `map`、`filter`、列表推导式等)简化代码。
                        5. 对于简单逻辑，使用 `lambda` 函数代替 `def`。
                        6. 移除不必要的条件判断或合并条件。
                        7. 如果有mermaid不要修改mermaid!!!!!!
                        8. 保留原有格式、顺序和标题!!!
                    # 结果限定在{limit_str_num}个token以内!!!!!!!!!!!!!!!
                    # 只输出简化后的结果!!!!不要输出额外信息!!!!!!!
                """.lstrip(),
        }
        invoke_result = await self.ainvoke([prompt_result])
        result_text = invoke_result["content"].lstrip()
        str_num = self.count_tokens(result_text)
        print(f"token缩减: {recursion_count} 轮次")
        print(f"简化{str_num_before}: {text}")
        print(f"简化后{str_num}: {result_text}")
        if str_num <= limit_str_num:
            return result_text
        return await self.trans_in_limit(
            result_text, limit_str_num, recursion_count + 1
        )

 
    async def ainvoke(self, messages: list[dict[str, str]]) -> list[str, str]:
        """
        发送消息并获取响应。

        :param messages: 消息列表，每个消息是一个字典，包含角色和内容
        :return: 响应消息
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.chat_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        try:
            response_json =await self._send_request_async(
                self.chat_url, headers, data
            )
            return response_json["choices"][0]["message"]
        except Exception as e:
            print(f"Error processing messages: {e}")
            raise

    async def invoke_async_stream(
        self, messages: list[dict[str, str]], stream: bool = False
    ) -> list[str, str]:
        """
        发送消息并获取响应。

        :param messages: 消息列表，每个消息是一个字典，包含角色和内容
        :return: 响应消息
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.chat_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "stream": True,
        }

        try:
            response = self._send_request_async_stream(self.chat_url, headers, data)
            async for chunk in response:
                if chunk:  # 过滤掉空行
                    decoded_line = chunk.decode("utf-8")  # 解码字节流
                    if decoded_line.startswith("data:"):  # 检查是否为数据行
                        json_data = decoded_line.replace("data: ", "")  # 去掉前缀
                        if json_data.strip() == "[DONE]":  # 检查是否结束
                            # print("Stream finished.")
                            yield content  # noqa: F821
                            break
                        try:
                            response_data = json.loads(json_data)  # 解析 JSON
                            content = response_data["choices"][0]["delta"].get(
                                "content", ""
                            )
                            yield content
                        except json.JSONDecodeError:
                            print("Error decoding JSON:", json_data)
        except Exception as e:
            print(f"Error processing messages: {e}")
            raise

    def count_tokens(self, text):
        """
        通用的token计数器，支持中英日文和标点符号。
        :param text: 输入的文本
        :return: token的数量
        """
        # 正则表达式匹配：
        # 1. 中文字符(包括汉字)
        # 2. 日文字符(平假名、片假名、日文汉字)
        # 3. 英文字符(单词)
        # 4. 标点符号(中英文标点)
        # 5. 其他字符(如数字、特殊符号等)
        tokens = re.findall(
            r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]|\w+|[^\w\s]", text, re.UNICODE
        )
        # 返回token的数量
        return len(tokens)

    def truncate_text_to_tokens(self, text: str, limit_str_num: int = 8192) -> str:
        """
        截取文本的前limit_str_num个token。
        :param text: 输入的文本
        :param limit_str_num: token限制
        :return: 截取后的文本
        """
        tokens = re.findall(
            r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]|\w+|[^\w\s]", text, re.UNICODE
        )
        truncated_tokens = tokens[:limit_str_num]
        return "".join(truncated_tokens)

    async def _send_request_async_stream(
        self, url: str, headers: dict, data: dict, total=60
    ) -> requests.Response:
        """
        发送异步 HTTP POST 请求。

        :param url: 请求的目标 URL。
        :param headers: 请求头，包含认证信息和其他元数据。
        :param data: 请求体，通常是一个 JSON 格式的字典。
        :param stream: 是否启用流式传输。如果为 True，则返回流式响应对象。
        :return: 返回一个 `requests.Response` 对象，包含服务器的响应。
        """
        timeout = aiohttp.ClientTimeout(total=total)  # 设置超时时间
        try:
            con = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=con, trust_env=True, timeout=timeout
            ) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_message = await response.text()
                        raise Exception(
                            f"HTTP error: {response.status} - {error_message}"
                        )
                    # 返回解析后的 JSON 数据
                    async for chunk in response.content:
                        yield chunk
        except aiohttp.ClientConnectorError as e:
            raise Exception(f"Connection error: {e}")
        except asyncio.TimeoutError:
            raise Exception("Request timed out")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")

    async def _send_request_async(
        self, url: str, headers: dict, data: dict, total=200
    ) -> requests.Response:
        """
        发送异步 HTTP POST 请求。

        :param url: 请求的目标 URL。
        :param headers: 请求头，包含认证信息和其他元数据。
        :param data: 请求体，通常是一个 JSON 格式的字典。
        :param stream: 是否启用流式传输。如果为 True，则返回流式响应对象。
        :return: 返回一个 `requests.Response` 对象，包含服务器的响应。
        """
        timeout = aiohttp.ClientTimeout(total=total)  # 设置超时时间
        try:
            con = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(
                connector=con, trust_env=True, timeout=timeout
            ) as session:
                async with session.post(url, headers=headers, json=data) as response:
                    if response.status != 200:
                        error_message = await response.json()
                        raise Exception(
                            f"HTTP error: {response.status} - {error_message}"
                        )
                    # 返回解析后的 JSON 数据
                    return await response.json()
        except aiohttp.ClientConnectorError as e:
            raise Exception(f"Connection error: {e}")
        except asyncio.TimeoutError:
            raise Exception("Request timed out")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")


    async def invoke_stream2(self, messages):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {"model": self.chat_model, "messages": messages, "temperature": 0}
        con = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=con, trust_env=True) as session:
            async with session.post(self.chat_url, headers=headers, json=data) as resp:
                response_json = await resp.json()
                return response_json["choices"][0]["message"]["content"]


# 运行示例
if __name__ == "__main__":
    # pass
    # 引入路径
    import sys, pathlib

    [
        sys.path.append(str(pathlib.Path(__file__).resolve().parents[i]))
        for i in range(4)
    ]
    # self
    from config.index import conf

    # 示例使用
    async def main():
        # 获取ai_api
        openai_set = conf["ai"]["openai"]
        # openai_set = conf["ai"]["aihubmix"]
        client = OpenAIClient(
            api_key=openai_set["api_key"],
            chat_url=openai_set["chat_url"],
            chat_model=openai_set["chat_model"],
            embedding_url=openai_set["embedding_url"],
            embedding_model=openai_set["embedding_model"],
        )
        # # 测试 embedding 方法
        # text = "Hello, how are you?"
        # embedding = await client.embedding(text)
        # print(f"Embedding: {embedding}")

        # 测试 ainvoke 方法
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "写一个100字的小说"},
        ]
        response_message = await client.ainvoke(messages)
        print(f"Response: {response_message['content']}")
        # # 使用流式返回
        response_messages =  client.invoke_async_stream(messages)
        async for response_message in response_messages:
            print(f"Response: {response_message}")
    asyncio.run(main())
