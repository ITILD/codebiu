from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class DocumentChunkPrompt:
    async def get_strategy_prompt(self, filename: str, markdown_content: str) -> str:
        """
        获取分块策略推荐 Prompt
        """
        CHUNK_STRATEGY_PROMPT = """
你是一个专业的 RAG 文档分析专家。
请根据提供的文件名和文档开头片段，判断该文档最适合哪种文本分块（Chunking）策略，如无特殊内容默认通用分块策略。
输出JSON格式，不要包含任何额外的解释性文字**。
"""
        return [
            SystemMessage(content=CHUNK_STRATEGY_PROMPT),
            HumanMessage(content=f"文件名: {filename}\n文档开头片段: {markdown_content[:1000]}"),
        ]
