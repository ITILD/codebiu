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
    """RAGFlow 风格通用分块器

    处理逻辑:
    1. 遍历原始 Chunk 列表, 按内容类型分为"可合并"和"独立"两组
    2. 连续的可合并 Chunk 通过 naive_merge 合并为目标 token 大小
    3. 独立类型 Chunk (表格/图片) 携带上文构成完整语义块 (便于向量化和关键词检索):
       - pending 纯标题: 标题直接作为块前缀
       - 文档流最近的标题: 复制为块前缀 (语义锚点, 即使已被前文块消耗)
       - 无标题: 按重叠比例从最近文本块尾部取重叠文本
    4. 保持原始文档顺序
    """

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        if not chunks:
            return []

        results: list[ChunkedItem] = []
        pending_merge: list[Chunk] = []
        pending_tokens = 0

        # 与 naive_merge 一致的封存阈值: 缓冲区累积接近 token 上限时才在标题边界切分,
        # 避免每个小节独立成块导致块远小于 chunk_token_num
        overlap = max(0, min(int(self.config.overlapped_percent or 0), 99))
        threshold = self.config.chunk_token_num * (100 - overlap) / 100.0

        # 文档流中最近出现的标题链 (连续标题累积, 如 "1.4. 音视频" + "1.5. 图表";
        # 新标题(前面非标题)到达时重置), 作为图片/表格独立块的上文来源
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
            """无标题时, 从最近的文本块尾部按重叠比例取上文 (对齐 naive_merge 的块间重叠)"""
            if overlap <= 0:
                return ""
            for item in reversed(results):
                if not all(ct in mergeable_values for ct in item.content_types):
                    continue  # 跳过独立块(表格/图片), 只取文本块
                text = item.content or ""
                overlap_len = int(len(text) * overlap / 100)
                if overlap_len <= 0:
                    return ""
                return text[-overlap_len:].strip()
            return ""

        i = 0
        while i < len(chunks):
            chunk = chunks[i]
            content = (chunk.content or "").strip()
            if not content:
                i += 1
                continue

            if chunk.content_type in _MERGEABLE_TYPES:
                # 标题对齐切分: 缓冲区已接近 token 上限时, 在标题前封存,
                # 让标题与其后内容开启新块 (避免标题成为上一块尾部);
                # 缓冲区不足时标题继续入队, 与前后正文合并填满整块
                # (连续标题仍可互相合并, 如 "1.4. 音视频" + "1.5. 图表")
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

            # 不可合并类型 (表格/图片): 独立成块并携带上文
            # 摘取 pending 尾部的连续标题作为块前缀 (标题归属于紧随的图片/表格,
            # 参考 ragflow naive_merge_docx 的 section title 归属语义):
            # 避免标题随文本 flush 进上一块后又复制为独立块前缀, 造成跨块重复
            title_sources: list[Chunk] = []
            if pending_merge:
                k = len(pending_merge)
                while k > 0 and pending_merge[k - 1].content_type == ContentType.TITLE:
                    k -= 1
                if k < len(pending_merge):
                    title_sources = pending_merge[k:]
                    pending_merge = pending_merge[:k]
            _flush_merge()

            # 吸收紧随其后的同源图片描述 (metadata.image_path 相同的 image_content):
            # 图片引用 ![](...) 与其 OCR/VLM 文字描述本属同一语义单元,
            # 合并为一个完整块, 避免同一张图的内容被拆进两个块
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

            # 上文: 已消费标题则内容自带; 否则带最近标题链(复制, 语义锚点);
            # 无标题则按重叠比例取前文文本尾部 (与文本块间重叠一致)
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

        # 为独立内容块附加下文上下文 (上文已由标题前缀/重叠尾部携带, 不再重复附加)
        results = attach_context(
            results, self.config.context_token_num, with_above=False
        )

        return results
