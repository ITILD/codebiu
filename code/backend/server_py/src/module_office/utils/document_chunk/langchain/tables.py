"""LangChain 风格表格分块器

使用 langchain 的 RecursiveCharacterTextSplitter 处理文本部分,
表格部分保持与 ragflow 引擎相同的表头上下文注入策略。
独立表格块附带前文上下文。
"""

from __future__ import annotations

from module_office.utils.document_chunk.base import BaseChunker, register_chunker
from module_office.utils.document_chunk.do.chunk import ChunkStrategyEnum, ChunkedItem, build_item
from module_office.utils.document_chunk.langchain.general import LangChainGeneralChunker
from module_office.utils.document_chunk.ragflow.nlp import (
    attach_context,
    count_tokens,
    hard_split_by_token_limit,
)
from module_office.utils.file_parase.do.chunk import Chunk, ContentType

_MERGEABLE_TYPES = {ContentType.TEXT, ContentType.IMAGE_CONTENT}


@register_chunker("langchain", ChunkStrategyEnum.TABLES)
class LangChainTableChunker(BaseChunker):
    """LangChain 风格表格分块器

    表格处理策略与 RAGFlowTableChunker 一致:
    - TABLE_SHEET / TABLE_HEADER 作为上下文注入
    - TABLE / TABLE_CONTENT 保持结构完整性
    - 文本部分使用 langchain splitter 合并
    - 独立块附带前文上下文
    """

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        if not chunks:
            return []

        general_chunker = LangChainGeneralChunker(self.config)
        splitter = general_chunker._build_splitter()

        results: list[ChunkedItem] = []
        pending: list[Chunk] = []
        current_sheet = ""
        current_header = ""

        def _flush_pending() -> None:
            nonlocal pending
            if pending:
                merged = general_chunker.merge_chunks(pending, splitter)
                results.extend(merged)
                pending = []

        for chunk in chunks:
            content = (chunk.content or "").strip()
            if not content:
                continue

            ct = chunk.content_type

            if ct == ContentType.TABLE_SHEET:
                _flush_pending()
                current_sheet = content
                current_header = ""
                continue

            if ct == ContentType.TABLE_HEADER:
                _flush_pending()
                current_header = content
                continue

            if ct == ContentType.TABLE:
                _flush_pending()
                results.extend(self._process_table(chunk, current_sheet))
                continue

            if ct == ContentType.TABLE_CONTENT:
                _flush_pending()
                results.extend(
                    self._process_table_content(chunk, current_sheet, current_header)
                )
                continue

            if ct in _MERGEABLE_TYPES:
                pending.append(chunk)
                continue

            _flush_pending()
            results.append(self._chunk_to_item(chunk))

        _flush_pending()

        # 为独立内容块附加上文上下文
        results = attach_context(results, self.config.context_token_num)

        return results

    def _process_table(self, chunk: Chunk, sheet: str) -> list[ChunkedItem]:
        content = (chunk.content or "").strip()
        if count_tokens(content) <= self.config.chunk_token_num:
            item = self._chunk_to_item(chunk)
            if sheet:
                item.metadata = {**(item.metadata or {}), "sheet": sheet}
            return [item]

        hard_limit = int(self.config.chunk_token_num * 1.5)
        parts = hard_split_by_token_limit(content, self.config.chunk_token_num, hard_limit)
        items = []
        for part in parts:
            if part.strip():
                item = build_item(part, [chunk])
                if sheet:
                    item.metadata = {**(item.metadata or {}), "sheet": sheet}
                items.append(item)
        return items

    def _process_table_content(
        self, chunk: Chunk, sheet: str, header: str
    ) -> list[ChunkedItem]:
        content = (chunk.content or "").strip()
        if not content:
            return []

        context_parts = []
        if sheet:
            context_parts.append(f"[所属工作表: {sheet}]")
        if header:
            context_parts.append(header)
        prefix = "\n".join(context_parts)

        if count_tokens(content) <= self.config.chunk_token_num:
            full = f"{prefix}\n{content}" if prefix else content
            item = build_item(full, [chunk])
            if sheet:
                item.metadata = {**(item.metadata or {}), "sheet": sheet}
            return [item]

        hard_limit = int(self.config.chunk_token_num * 1.5)
        parts = hard_split_by_token_limit(content, self.config.chunk_token_num, hard_limit)
        items = []
        for part in parts:
            if part.strip():
                full = f"{prefix}\n{part}" if prefix else part
                item = build_item(full, [chunk])
                if sheet:
                    item.metadata = {**(item.metadata or {}), "sheet": sheet}
                items.append(item)
        return items

    def _chunk_to_item(self, chunk: Chunk) -> ChunkedItem:
        return ChunkedItem(
            content=(chunk.content or "").strip(),
            content_types=[chunk.content_type.value] if chunk.content_type else [],
            position=chunk.position,
            source=chunk.metadata.get("source", "") if chunk.metadata else "",
            metadata=chunk.metadata,
        )
