from langchain_core.messages import HumanMessage, SystemMessage


class LLMBasePrompt:
    async def get_prompt_format_check(self):
        prompt_result = SystemMessage(
            # 校验格式化。
            content="""There is a person named Bill and he is 100 years old.""".strip()
        )
        return prompt_result
