import os
import numpy as np
import re
import tiktoken

from config.index import tiktoken_cache_dir

tiktoken_path = tiktoken_cache_dir / "tiktoken"
os.environ["TIKTOKEN_CACHE_DIR"] = str(tiktoken_path)
tiktokenenc = tiktoken.get_encoding("cl100k_base")

class LLMUtils:
    @classmethod
    def count_tokens(cls, text):
        tokens = tiktokenenc.encode(text)
        return len(tokens)

    @classmethod
    def clean_prompt(cls, prompt: str) -> str:
        # 移除多余空格、换行等
        prompt = re.sub(r"\s+", " ", prompt).strip()
        return prompt

    @classmethod
    def embeddings_info(cls, embeddings_result):
        """_summary_: 获取向量化模型信息

        Args:
            embeddings_result (_type_):

        Returns:
            _type_: _description_
        """
        vector = np.array(embeddings_result)  # 转换为 NumPy 数组
        norm = np.linalg.norm(vector)  # 计算 L2 范数
        # 判断是否归一化
        tolerance = 1e-6  # 设置容差范围，处理浮点数精度问题
        is_normalized_bool = abs(norm - 1.0) < tolerance
        return {
            # 归一化
            "norm": norm,
            "normalized": is_normalized_bool,
            # 维度
            "len": len(vector),
        }

    # 向量归一化
    @classmethod
    def normalize_vector(cls, vector: list[float]):
        norm = np.linalg.norm(vector)
        return vector / norm if norm != 0 else vector

    @classmethod
    async def embedding_in_limit(
        cls, llm, embeddings, text: str, limit_str_num: int = 8192
    ) -> list[float]:
        try:
            text = await cls.trans_in_limit(llm, text, limit_str_num)
            return await embeddings.aembed_query(text)
        except Exception as e:
            print(f"embedding_in_limit error: {e}")
            raise e

    @classmethod
    async def trans_in_limit(
        cls, llm, text: str, limit_str_num: int = 8192, recursion_count: int = 0
    ) -> list[str, str]:
        # 如果递归次数超过3次，直接截取前limit_str_num个token的字符串
        if recursion_count >= 3:
            return cls.truncate_text_to_tokens(text, limit_str_num)
        # tokens数限制
        str_num_before = cls.count_tokens(text)
        if str_num_before <= limit_str_num:
            return text
        # 去除空格换行 tokens数限制
        text = text.lstrip()
        str_num_before = cls.count_tokens(text)
        if str_num_before <= limit_str_num:
            return text
        prompt_result = {
            "role": "system",
            "content": f"""
                    # 请缩略待处理内容的代码和信息，同时确保不丢失主要信息，保留原有格式、顺序和标题!!!缩略时请遵循以下规则：
                        1. 删除不必要的注释(非业务功能注释)和空行。
                        2. 使用简短的变量名(确保变量名仍有意义)。
                        3. 合并可以简化的语句。
                        4. 使用内置函数或库(如 `map`、`filter`、列表推导式等)简化代码。
                        5. 对于简单逻辑，使用 `lambda` 函数代替。
                        6. 移除不必要的条件判断或合并条件。
                        7. 如果有mermaid不要修改mermaid!!!!!!
                        8. 保留原有格式、顺序和标题!!!
                    # 结果限定在{limit_str_num}个token以内!!!!!!!!!!!!!!!
                    # 只输出简化后的结果!!!!不要输出额外信息!!!!!!!
                    # 待处理内容
                        {text} 
                """.lstrip(),
        }
        invoke_result = await llm.ainvoke([prompt_result])
        result_text = invoke_result.lstrip()
        str_num = cls.count_tokens(result_text)
        print(f"token缩减: {recursion_count} 轮次")
        # print(f"简化{str_num_before}: {text}")
        # print(f"简化后{str_num}: {result_text}")
        if str_num <= limit_str_num:
            return result_text
        print(f"token缩减继续缩减")
        return await cls.trans_in_limit(
            llm, result_text, limit_str_num, recursion_count + 1
        )

    @classmethod
    def truncate_text_to_tokens(cls, text: str, limit_str_num: int = 8192) -> str:
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


if __name__ == "__main__":
    text = "测试test"
    len_1 = LLMUtils.count_tokens(text)
    print(len_1)
