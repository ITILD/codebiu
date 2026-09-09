from langchain_openai import ChatOpenAI
from langchain_core.outputs import  ChatGenerationChunk

class ChatQwenWithReasoning(ChatOpenAI):
    """同时支持流式/非流式提取 reasoning_content 的 ChatOpenAI 子类"""

    # --- 非流式: 拦截
    # --- 流式: 拦截 _convert_chunk_to_generation_chunk ---
    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """从流式 chunk 中提取 reasoning_content"""
        gen_chunk = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if gen_chunk is None:
            return None

        # 从原始 chunk dict 的 delta 中提取非标准字段
        choices = chunk.get("choices", [])
        if choices and isinstance(choices[0].get("delta"), dict):
            reasoning = choices[0]["delta"].get("reasoning_content")
            if reasoning:
                gen_chunk.message.reasoning_content = reasoning
                print('test:', reasoning)

        return gen_chunk
