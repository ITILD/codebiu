from langchain_core.output_parsers import BaseTransformOutputParser
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableLambda


class TooLongRunnable:
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
        """可能丢失部分细节"""
        # Map阶段
        map_prompt = ChatPromptTemplate.from_template(map_prompt_str)
        map_chain = map_prompt | self.llm | RunnableLambda(lambda x: x.content)

        # Reduce阶段
        reduce_prompt = ChatPromptTemplate.from_template("合并以下部分信息:\n\n{text}")
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

    # @staticmethod
    # def refine(llm=None) -> RunnableLambda:
    #     """上下文连贯性最佳"""
    #     llm = llm or ChatOpenAI()

    #     refine_prompt = ChatPromptTemplate.from_template(
    #         "请逐步完善以下文本，保持上下文连贯:\n\n{text}"
    #     )
    #     refine_chain = refine_prompt | llm | RunnableLambda(lambda x: x.content)

    #     def refine_func(input_text: str) -> str:
    #         return refine_chain.invoke({"text": input_text})

    #     return RunnableLambda(refine_func)


if __name__ == "__main__":
    import asyncio
    from config.index import conf
    import logging
logger = logging.getLogger(__name__)
    from module_ai.utils.llm.do.llm_config import OllamaConfig
    from module_ai.utils.llm.ai_factory import AIFactory
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    async def main():
        qusetion_test = "直接回答结果数字 1+1=?"

    asyncio.run(main())
