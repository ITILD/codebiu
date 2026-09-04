from langchain_core.messages import HumanMessage, SystemMessage


class LLMBasePrompt:
    """LLM基础服务提示词构造器"""

    async def get_prompt_format_check(self):
        """构造格式校验提示词(用于检验模型是否遵循输出格式要求)"""
        prompt_result = SystemMessage(
            # 校验格式化。
            content="""There is a person named Bill and he is 100 years old.""".strip()
        )
        return prompt_result
