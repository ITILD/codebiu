from module_ai.do.translate import Translate
from langchain_core.messages import HumanMessage, SystemMessage


class TranslatePrompt:
    async def get_prompt_system(self):
        prompt_result = SystemMessage(
            # 你是一个精通多种语言的翻译，请按要求将提供的内容翻译成对应语言，保留阿拉伯数字等特殊字符。
            content="""
You are a translator proficient in multiple languages. 
Please translate the provided content into the specified language while preserving special characters such as Arabic numerals.
""".strip()
        )
        return prompt_result

    # 减少截断影响，需求放前面
    async def get_prompt_user(self, translate: Translate):
        prompt_result = HumanMessage(
            #  将 以下内容{translate.content} 翻译成 {translate.lang} 语言。
            content=f"""
Translate the provided content into {translate.lang.full_name} language.
The provided content is text recognized by OCR, and there may be incorrectly recognized characters,
Please quietly correct and output its original meaning.
Only output the translation result, do not output any extra content!!!!
Provided content:{translate.content}
""".strip()
        )
        return prompt_result
