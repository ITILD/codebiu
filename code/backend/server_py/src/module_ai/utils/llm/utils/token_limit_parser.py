from langchain_core.output_parsers import BaseTransformOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import BaseMessage
from module_ai.utils.llm.utils.llm_utils import LLMUtils


class TokenLimitParser(BaseTransformOutputParser):
    """
    限制token数量
    """

    def __init__(self, input_tokens: int):
        super().__init__()
        self._input_tokens = input_tokens

    def parse(self, text):
        return text

    def get_check_token_limit_base_runnable(self) -> RunnableLambda:
        # 输入
        # 定义处理函数：
        def add_runnable_lambda(input_data: list | str) -> list | str:
            if isinstance(input_data, list) and input_data:
                # 处理列表情况
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
                            elif isinstance(item, BaseMessage) and hasattr(
                                item, "content"
                            ):
                                item.content = self._truncate_text_by_tokens(
                                    str(item.content), remaining_tokens
                                )
                            else:
                                item = self._truncate_text_by_tokens(
                                    str(item), remaining_tokens
                                )
                            result.append(item)
                        break
            else:
                # 处理字符串情况
                input_data_str = str(input_data)
                input_data_len = LLMUtils.count_tokens(input_data_str)
                if input_data_len > self._input_tokens:
                    input_data = self._truncate_text_by_tokens(
                        input_data_str, self._input_tokens
                    )
                result = input_data
            return result

        # 封装为 RunnableLambda
        return RunnableLambda(add_runnable_lambda)

    def _truncate_text_by_tokens(self, text: str, _input_tokens: int) -> str:
        """
        根据token数量截断文本

        参数:
            text: 要截断的文本
            _input_tokens: 最大token数量

        返回:
            截断后的文本
        """
        # 这是一个简化的实现，实际实现可能需要更复杂的token计算和截断逻辑
        # 这里假设我们可以简单地按字符比例截断（不精确）
        current_tokens = LLMUtils.count_tokens(text)
        if current_tokens <= _input_tokens:
            return text

        ratio = _input_tokens / current_tokens
        max_chars = int(len(text) * ratio)
        # max_chars = min(max_chars,_input_tokens)
        # print(f"token数量: {current_tokens}. 长度: {len(text)} ")
        # print(f"截断后token{LLMUtils.count_tokens(text[:max_chars])} 截断后长度: {max_chars}")
        return text[:max_chars]


if __name__ == "__main__":
    import asyncio
    from config.index import conf
    import logging
logger = logging.getLogger(__name__)
    from module_ai.utils.llm.do.llm_config import OllamaConfig
    from module_ai.utils.llm.ai_factory import AIFactory
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from config.ai import llm_chat

    async def main():
        qusetion = "请将最后一个数字返给我"
        for i in range(10000):
            qusetion += f"{i}_"
        qusetion_list = [
            SystemMessage(content="你是一个数学家"),
            HumanMessage(content=qusetion),
        ]
        result = await llm_chat.ainvoke(qusetion)
        print(result)
        result = await llm_chat.ainvoke(qusetion_list)
        print(result)

    asyncio.run(main())
