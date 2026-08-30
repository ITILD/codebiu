"""Python/Java 专用代码分块器。"""

from __future__ import annotations

from module_office.utils.document_chunk.base import BaseChunker, register_chunker
from module_office.utils.document_chunk.do.chunk import ChunkStrategyEnum, ChunkedItem
from module_office.utils.document_chunk.ragflow.nlp import count_tokens, hard_split_by_token_limit
from module_office.utils.file_parase.do.chunk import Chunk, ContentType, Position


@register_chunker("ragflow", ChunkStrategyEnum.CODE)
@register_chunker("langchain", ChunkStrategyEnum.CODE)
class CodeChunker(BaseChunker):
    """保持符号边界，超长符号仅在行边界继续拆分。"""

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        results: list[ChunkedItem] = []
        for chunk in chunks:
            content = (chunk.content or "").strip()
            if not content:
                continue
            parts = self._split_code(content)
            total = len(parts)
            for index, (part, start_offset, end_offset) in enumerate(parts):
                metadata = dict(chunk.metadata or {})
                metadata["part_index"] = str(index)
                metadata["part_count"] = str(total)
                results.append(
                    ChunkedItem(
                        content=part,
                        content_types=[ContentType.CODE.value],
                        position=self._part_position(
                            chunk.position, start_offset, end_offset
                        ),
                        source=metadata.get("source", ""),
                        metadata=metadata,
                    )
                )
        return results

    def _split_code(self, content: str) -> list[tuple[str, int, int]]:
        limit = max(1, self.config.chunk_token_num)
        if count_tokens(content) <= limit:
            return [(content, 0, max(0, content.count("\n")))]

        lines = content.splitlines()
        if not lines:
            return [(part, 0, 0) for part in hard_split_by_token_limit(content, limit)]

        parts: list[tuple[str, int, int]] = []
        current: list[tuple[str, int]] = []
        current_tokens = 0
        overlap_percent = min(max(self.config.overlapped_percent, 0), 50)

        def _finalize() -> None:
            if not current:
                return
            text = "\n".join(line for line, _ in current).strip()
            if text:
                parts.append((text, current[0][1], current[-1][1]))

        for line_index, line in enumerate(lines):
            line_tokens = count_tokens(line)
            if line_tokens > limit:
                if current:
                    _finalize()
                    current = []
                    current_tokens = 0
                parts.extend(
                    (part, line_index, line_index)
                    for part in hard_split_by_token_limit(line, limit)
                )
                continue

            if current and current_tokens + line_tokens > limit:
                _finalize()
                overlap_lines = max(0, int(len(current) * overlap_percent / 100))
                current = current[-overlap_lines:] if overlap_lines else []
                current_tokens = sum(count_tokens(item) for item, _ in current)

            current.append((line, line_index))
            current_tokens += line_tokens

        if current:
            _finalize()
        return parts

    @staticmethod
    def _part_position(
        position: Position, start_offset: int, end_offset: int
    ) -> Position:
        if not position.text_range:
            return position.model_copy(deep=True)
        start_line = position.text_range[0]
        part_start = start_line + start_offset
        part_end = start_line + end_offset
        return position.model_copy(
            update={"text_range": [part_start, 0, part_end, 0]}, deep=True
        )
