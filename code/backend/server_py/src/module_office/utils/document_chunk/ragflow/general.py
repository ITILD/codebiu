"""RAGFlow 风格通用分块器

参考 ragflow/app/naive.py 的 chunk() 函数业务逻辑:
- 将文本/标题类 Chunk 通过 naive_merge 合并为目标大小的块
- 表格/图片类 Chunk 保持独立, 但附加上文上下文增强向量关联
  (参考 ragflow naive_merge_docx 的 table_context_size / image_context_size)

改进点 (对比原 chunk_strategy 和旧 RAGFlowLikeChunker):
- 直接在 Chunk 对象上操作, 无需 markdown 往返转换
- 原生保留位置信息 (bbox / page / heading_level)
- 独立内容块附带前文上下文, 提高向量检索召回率
"""

from __future__ import annotations

from module_office.utils.document_chunk.base import BaseChunker, register_chunker
from module_office.utils.document_chunk.do.chunk import (
    ChunkStrategyEnum,
    ChunkedItem,
    build_item,
)
from module_office.utils.document_chunk.ragflow.nlp import (
    attach_context,
    count_tokens,
    naive_merge,
)
from module_office.utils.file_parase.do.chunk import Chunk, ContentType

# 可合并的内容类型 (文本类, 合并后不会丢失语义)
_MERGEABLE_TYPES = {ContentType.TEXT, ContentType.IMAGE_CONTENT, ContentType.TITLE}


@register_chunker("ragflow", ChunkStrategyEnum.GENERAL)
class RAGFlowGeneralChunker(BaseChunker):
    """RAGFlow 风格通用分块器 (优化版: 减少碎块)"""

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        if not chunks:
            return []

        results: list[ChunkedItem] = []
        pending_merge: list[Chunk] = []
        pending_tokens = 0

        overlap = max(0, min(int(self.config.overlapped_percent or 0), 99))
        threshold = self.config.chunk_token_num * (100 - overlap) / 100.0
        
        # 【优化点 1】小独立块合并阈值: 低于此 token 数的表格/图片描述将降级为可合并类型
        # 避免小表格频繁打断文本流导致产生大量碎块, 使其参与 naive_merge 填满 Chunk
        SMALL_STANDALONE_THRESHOLD = int(self.config.chunk_token_num * 0.3)

        last_titles: list[str] = []
        prev_type: ContentType | None = None
        mergeable_values = {t.value for t in _MERGEABLE_TYPES}

        def _flush_merge() -> None:
            nonlocal pending_merge, pending_tokens
            if pending_merge:
                merged = naive_merge(
                    pending_merge,
                    chunk_token_num=self.config.chunk_token_num,
                    delimiter=self.config.delimiter,
                    overlapped_percent=self.config.overlapped_percent,
                )
                results.extend(merged)
                pending_merge = []
            pending_tokens = 0

        def _overlap_tail() -> str:
            """无标题时, 从最近的文本块尾部按重叠比例取上文"""
            if overlap <= 0:
                return ""
            for item in reversed(results):
                if not all(ct in mergeable_values for ct in item.content_types):
                    continue
                text = item.content or ""
                overlap_len = int(len(text) * overlap / 100)
                if overlap_len <= 0:
                    return ""
                return text[-overlap_len:].strip()
            return ""

        def _is_pure_image_chunk(c: Chunk) -> bool:
            """判断是否为纯图片 (无文本语义, 必须独立)"""
            return c.content_type == ContentType.IMAGE and not (c.content or "").strip()

        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            content = (chunk.content or "").strip()
            if not content:
                i += 1
                continue

            if chunk.content_type in _MERGEABLE_TYPES:
                # 标题对齐切分: 缓冲区已接近 token 上限时, 在标题前封存
                if (
                    chunk.content_type == ContentType.TITLE
                    and pending_merge
                    and pending_tokens >= threshold
                    and any(c.content_type != ContentType.TITLE for c in pending_merge)
                ):
                    _flush_merge()
                    
                if chunk.content_type == ContentType.TITLE:
                    if prev_type == ContentType.TITLE:
                        last_titles.append(content)
                    else:
                        last_titles = [content]
                        
                pending_merge.append(chunk)
                pending_tokens += count_tokens(content)
                prev_type = chunk.content_type
                i += 1
                continue

            # 【优化点 1 核心逻辑】不可合并类型 (表格/图片) 的动态处理
            chunk_tokens = count_tokens(content)
            is_pure_img = _is_pure_image_chunk(chunk)
            
            # 若独立块 token 数较小且非纯图片, 降级为可合并类型, 不打断文本流
            if not is_pure_img and chunk_tokens <= SMALL_STANDALONE_THRESHOLD:
                pending_merge.append(chunk)
                pending_tokens += chunk_tokens
                prev_type = chunk.content_type
                i += 1
                continue

            # 否则, 保持独立, 走原有的打断逻辑
            title_sources: list[Chunk] = []
            if pending_merge:
                k = len(pending_merge)
                while k > 0 and pending_merge[k - 1].content_type == ContentType.TITLE:
                    k -= 1
                if k < len(pending_merge):
                    title_sources = pending_merge[k:]
                    pending_merge = pending_merge[:k]
            _flush_merge()

            # 吸收紧随其后的同源图片描述
            group = [chunk]
            image_path = (chunk.metadata or {}).get("image_path", "")
            j = i + 1
            while (
                image_path
                and j < len(chunks)
                and chunks[j].content_type == ContentType.IMAGE_CONTENT
                and (chunks[j].content or "").strip()
                and (chunks[j].metadata or {}).get("image_path", "") == image_path
            ):
                group.append(chunks[j])
                j += 1

            # 构建独立块的上文前缀
            parts: list[str] = [
                (c.content or "").strip()
                for c in title_sources
                if (c.content or "").strip()
            ]
            if not title_sources:
                if last_titles:
                    parts.append("\n".join(last_titles))
                else:
                    overlap_tail = _overlap_tail()
                    if overlap_tail:
                        parts.append(overlap_tail)
            parts.extend(
                (c.content or "").strip() for c in group if (c.content or "").strip()
            )

            results.append(build_item("\n".join(parts), title_sources + group))
            prev_type = chunk.content_type
            i = j

        _flush_merge()

        # 为独立内容块附加下文上下文
        results = attach_context(
            results, self.config.context_token_num, with_above=False
        )

        return results