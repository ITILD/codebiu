from typing import TypedDict, Union, Optional, Any
from common.utils.ai.common_splitter.text_splitter_utils import TextSplitterUtils


class ChunkSplited(TypedDict):
    text: str
    doc_index: int
    chunk_index: int


class DocumentsSplitterUtils:
    """通用文本和代码拆分器"""

    def __init__(
        self,
        input_tokens: int = 8192,
        chunk_tokens: int = 1024,
        chunk_length: int = 500,
    ):
        self.input_tokens = input_tokens
        self.chunk_tokens = chunk_tokens
        self.chunk_length = chunk_length
        # 单个 chunk 的 token 分割器
        self.splitter_utils = TextSplitterUtils(
            chunk_size=self.chunk_tokens, chunk_overlap=self.chunk_tokens // 20
        )

    async def split_documents(
        self,
        documents: list[Union[str, dict[str, Any]]],
        sort_key: Optional[str] = None,
    ) -> list[list[ChunkSplited]]:
        """异步拆分文档为分组的 chunks 列表"""
        all_chunks: list[ChunkSplited] = []
        for doc_idx, doc in enumerate(documents):
            content = self._extract_content(doc, sort_key)
            chunks = self.splitter_utils.split_text(content)
            for idx, chunk in enumerate(chunks):
                if chunk.strip():
                    all_chunks.append(
                        {"text": chunk, "doc_index": doc_idx, "chunk_index": idx}
                    )
        return self._group_chunks_into_batches(all_chunks)

    def _extract_content(self, doc: Union[str, dict], sort_key: Optional[str]) -> str:
        """从文档中提取文本内容"""
        if sort_key:
            if isinstance(doc, dict) and sort_key in doc:
                return str(doc[sort_key])
            elif hasattr(doc, sort_key):
                return str(getattr(doc, sort_key))
        return str(doc)

    def _group_chunks_into_batches(
        self, chunks: list[ChunkSplited]
    ) -> list[list[ChunkSplited]]:
        """将 chunks 按 token 限制和 top_n 限制分组"""
        batches = []
        current_batch = []
        current_token_count = 0

        for chunk in chunks:
            chunk_tokens = len(
                chunk["text"]
            )  # 注意：这里用字符数近似 token，实际应使用 tokenizer

            # 检查是否需要开启新批次
            if (
                current_token_count + chunk_tokens > self.input_tokens
                or len(current_batch) >= self.chunk_length
            ):
                batches.append(current_batch)
                current_batch = []
                current_token_count = 0

            current_batch.append(chunk)
            current_token_count += chunk_tokens

        # 添加最后一个批次(如果非空)
        if current_batch:
            batches.append(current_batch)
        return batches
