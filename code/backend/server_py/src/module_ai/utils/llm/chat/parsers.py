"""LangChain 输出/输入链路上的通用解析器

- TokenLimitParser: 输入 token 上限截断(列表逐条累计/单文本整体截断)
- TooLongRunnable: 超长文本 map-reduce 摘要压缩
"""
from langchain_core.messages import BaseMessage
from langchain_core.output_parsers import BaseTransformOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter

from module_ai.utils.llm.chat.utils import LLMUtils


class TokenLimitParser(BaseTransformOutputParser):
    """输入 token 数量限制器: 超限时按比例截断文本"""

    def __init__(self, input_tokens: int):
        super().__init__()
        self._input_tokens = input_tokens

    def parse(self, text):
        return text

    def get_check_token_limit_base_runnable(self) -> RunnableLambda:
        """构建输入侧 token 限制 Runnable(消息列表逐条累计, 单文本整体截断)"""

        def limit_tokens(input_data: list | str) -> list | str:
            if isinstance(input_data, list) and input_data:
                total_tokens = 0
                result = []
                for item in input_data:
                    item_tokens = LLMUtils.count_tokens(str(item))
                    if total_tokens + item_tokens <= self._input_tokens:
                        result.append(item)
                        total_tokens += item_tokens
                    else:
                        remaining_tokens = self._input_tokens - total_tokens
                        if remaining_tokens > 0:
                            if isinstance(item, dict) and "content" in item:
                                item["content"] = self._truncate_text_by_tokens(
                                    str(item["content"]), remaining_tokens
                                )
                            elif isinstance(item, BaseMessage) and hasattr(item, "content"):
                                item.content = self._truncate_text_by_tokens(
                                    str(item.content), remaining_tokens
                                )
                            else:
                                item = self._truncate_text_by_tokens(str(item), remaining_tokens)
                            result.append(item)
                        break
            else:
                input_data_str = str(input_data)
                if LLMUtils.count_tokens(input_data_str) > self._input_tokens:
                    input_data = self._truncate_text_by_tokens(input_data_str, self._input_tokens)
                result = input_data
            return result

        return RunnableLambda(limit_tokens)

    def _truncate_text_by_tokens(self, text: str, _input_tokens: int) -> str:
        """按 token 上限以字符比例近似截断(不精确但零依赖)"""
        current_tokens = LLMUtils.count_tokens(text)
        if current_tokens <= _input_tokens:
            return text
        ratio = _input_tokens / current_tokens
        max_chars = int(len(text) * ratio)
        return text[:max_chars]


class TooLongRunnable:
    """超长文本 map-reduce 压缩: 先分块提炼再合并(可能丢失部分细节)"""

    def __init__(self, max_size=1000, chunk_overlap=100, llm=None):
        self.llm = llm
        self.max_size = max_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_size, chunk_overlap=chunk_overlap
        )

    def map_reduce(
        self,
        map_prompt_str="输出限制在{max_token}token内,提取以下文本的关键信息:\n\n{text}",
        reduce_prompt_str="输出限制在{max_token}token内,合并以下部分信息:\n\n{text}",
    ) -> RunnableLambda:
        """构建 map-reduce 压缩链"""
        map_prompt = ChatPromptTemplate.from_template(map_prompt_str)
        map_chain = map_prompt | self.llm | RunnableLambda(lambda x: x.content)

        reduce_prompt = ChatPromptTemplate.from_template(reduce_prompt_str)
        reduce_chain = reduce_prompt | self.llm | RunnableLambda(lambda x: x.content)

        def map_reduce_func(input_text: str) -> str:
            chunks = self.text_splitter.split_text(input_text)
            mapped = [
                map_chain.invoke({"max_token": self.max_size, "text": chunk})
                for chunk in chunks
            ]
            combined = "\n\n".join(mapped)
            return reduce_chain.invoke({"max_token": self.max_size, "text": combined})

        return RunnableLambda(map_reduce_func)
