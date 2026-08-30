"""LangChain 风格通用分块器

使用 langchain 的 RecursiveCharacterTextSplitter 进行分块, 作为 ragflow 引擎的替代方案。
位置信息保留策略:
- 单个 Chunk 超限时, 用 splitter 拆分, 每个子块继承原 Chunk 的位置
- 相邻小 Chunk 合并时, 聚合位置信息
- 独立内容块附带前文上下文
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from module_office.utils.document_chunk.base import BaseChunker, register_chunker
from module_office.utils.document_chunk.do.chunk import ChunkStrategyEnum, ChunkedItem, build_item
from module_office.utils.document_chunk.ragflow.nlp import attach_context, count_tokens
from module_office.utils.file_parase.do.chunk import Chunk, ContentType

_MERGEABLE_TYPES = {ContentType.TEXT, ContentType.IMAGE_CONTENT}


@register_chunker("langchain", ChunkStrategyEnum.GENERAL)
class LangChainGeneralChunker(BaseChunker):
    """LangChain 风格通用分块器

    使用 RecursiveCharacterTextSplitter 递归拆分, 配合位置感知合并。
    """

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        if not chunks:
            return []

        splitter = self._build_splitter()

        results: list[ChunkedItem] = []
        pending: list[Chunk] = []

        def _flush_pending() -> None:
            nonlocal pending
            if not pending:
                return
            merged = self._merge_chunks(pending, splitter)
            results.extend(merged)
            pending = []

        for chunk in chunks:
            content = (chunk.content or "").strip()
            if not content:
                continue

            if chunk.content_type in _MERGEABLE_TYPES:
                pending.append(chunk)
            else:
                _flush_pending()
                results.append(self._chunk_to_item(chunk))

        _flush_pending()

        # 为独立内容块附加上文上下文
        results = attach_context(results, self.config.context_token_num)

        return results

    def _build_splitter(self) -> RecursiveCharacterTextSplitter:
        chunk_size = self.config.chunk_token_num * 3
        chunk_overlap = int(chunk_size * self.config.overlapped_percent / 100)
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[self.config.delimiter, "\n\n", "\n", "。", "；", "！", "？", " ", ""],
            keep_separator=True,
        )

    def merge_chunks(
        self, chunks: list[Chunk], splitter: RecursiveCharacterTextSplitter
    ) -> list[ChunkedItem]:
        """合并相邻小 Chunk, 拆分超长 Chunk (公开接口, 供 tables 复用)"""
        return self._merge_chunks(chunks, splitter)

    def _merge_chunks(
        self, chunks: list[Chunk], splitter: RecursiveCharacterTextSplitter
    ) -> list[ChunkedItem]:
        if not chunks:
            return []

        sub_sections: list[tuple[str, Chunk]] = []
        for chunk in chunks:
            text = (chunk.content or "").strip()
            if not text:
                continue

            if count_tokens(text) <= self.config.chunk_token_num:
                sub_sections.append((text, chunk))
            else:
                parts = splitter.split_text(text)
                for part in parts:
                    if part.strip():
                        sub_sections.append((part, chunk))

        if not sub_sections:
            return []

        results: list[ChunkedItem] = []
        current_texts: list[str] = []
        current_tokens = 0
        current_sources: list[Chunk] = []

        def _finalize() -> None:
            nonlocal current_texts, current_tokens, current_sources
            if current_texts:
                content = "\n".join(current_texts)
                if content.strip():
                    results.append(build_item(content, current_sources))
            current_texts = []
            current_tokens = 0
            current_sources = []

        for text, source in sub_sections:
            token_num = count_tokens(text)
            if current_texts and current_tokens + token_num > self.config.chunk_token_num:
                _finalize()
            current_texts.append(text)
            current_tokens += token_num
            current_sources.append(source)

        _finalize()
        return results

    def _chunk_to_item(self, chunk: Chunk) -> ChunkedItem:
        return ChunkedItem(
            content=(chunk.content or "").strip(),
            content_types=[chunk.content_type.value] if chunk.content_type else [],
            position=chunk.position,
            source=chunk.metadata.get("source", "") if chunk.metadata else "",
            metadata=chunk.metadata,
        )
