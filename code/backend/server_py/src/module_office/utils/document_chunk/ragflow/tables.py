"""RAGFlow 风格表格分块器

参考 ragflow/app/table.py 的表格处理逻辑:
- 表格内容按行切分, 每块携带 Sheet 名称 + 表头上下文
- Sheet 名称作为元数据注入

改进点 (对比原有 chunk_strategy/tables.py):
- 直接使用 Chunk.content_type 识别表格元素, 不依赖正则匹配 markdown
- 位置信息原生保留
- 与通用分块器共享合并逻辑, 文本部分同样按 token 上限合并
- 不再附加前后文上下文: 每个表格块已自带 Sheet+表头前缀,
  attach_context 的上文/下文注入会呈现为块间"伪重叠", 且会让
  邻块的行看起来被跨块拆分

分块行为:
- 单元格内换行(docling 多行单元格)先重组为逻辑表格行(换行保留 \\n),
  保证一个逻辑行不会被跨块切断
- 每个表格分块以 [所属工作表] + 表头(含 |---| 分隔行) 开头, 保证每块独立可读
- 表格内容按逻辑行逐行填充, 累计达到 chunk_token_num 上限后开启下一块
- 单行超限时: 默认将该行最大单元格一分为二拆成两行(保持表格结构),
  此模式不应用 overlapped_percent(每块均携带表头且行完整, 无需重叠);
  可通过 ChunkConfig.split_oversized_row_by_cell=False 改为直接按 token 硬切
  成多个独立块, 此模式下 overlapped_percent 生效(块间尾部文本重叠)
"""

from __future__ import annotations

import logging
import re

from module_office.utils.document_chunk.base import BaseChunker, register_chunker
from module_office.utils.document_chunk.do.chunk import ChunkStrategyEnum, ChunkedItem, build_item
from module_office.utils.document_chunk.ragflow.nlp import (
    count_tokens,
    hard_split_by_token_limit,
    naive_merge,
)
from module_office.utils.file_parase.do.chunk import Chunk, ContentType

logger = logging.getLogger(__name__)

_MERGEABLE_TYPES = {ContentType.TEXT, ContentType.IMAGE_CONTENT}

# markdown 表格行拆分: 未转义的 |
_MD_CELL_SPLIT = re.compile(r"(?<!\\)\|")


def _is_md_separator(line: str) -> bool:
    """判断是否为 markdown 表格分隔行 (|---|---| / |:---:|)"""
    s = line.strip()
    return bool(s) and "-" in s and set(s) <= set("|-: \t")


def _parse_md_row(line: str) -> list[str]:
    """拆分 markdown 表格行为单元格列表 (剥离首尾 |, 兼容转义 \\|)"""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in _MD_CELL_SPLIT.split(s)]


def _render_md_row(cells: list[str]) -> str:
    """将单元格列表渲染回紧凑 markdown 表格行"""
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def _split_text_halves(text: str) -> tuple[str, str]:
    """将文本一分为二; 优先在最接近中点的换行边界切(保持行完整),
    否则按 token 中点切; 无 token 边界时退化为字符中点
    """
    mid = len(text) // 2
    best_idx, best_dist = -1, None
    for m in re.finditer(r"\n", text):
        dist = abs(m.start() - mid)
        if best_dist is None or dist < best_dist:
            best_dist, best_idx = dist, m.start()
    if best_idx > 0:
        left, right = text[:best_idx].strip(), text[best_idx + 1 :].strip()
        if left and right:
            return left, right
    tokens = list(re.finditer(r"[A-Za-z0-9_]+|[一-鿿]", text))
    if len(tokens) >= 2:
        mid = tokens[len(tokens) // 2].start()
        left, right = text[:mid].strip(), text[mid:].strip()
        if left and right:
            return left, right
    mid = len(text) // 2
    return text[:mid].strip(), text[mid:].strip()


def _merge_logical_rows(lines: list[str]) -> list[str]:
    """将物理行重组为逻辑表格行 (单元格内换行保留 \\n)

    docling 输出的多行单元格会让一个逻辑表格行跨多个物理行:
    逻辑行以 | 开头, 单元格内换行产生的续行不以 | 开头。
    若不重组, 逐物理行分块会把一个逻辑行跨块切断, 且块内出现
    裸文本行破坏表格结构。重组后每行均为完整逻辑表格行。
    """
    logical: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("|") or not logical:
            logical.append(s)
        else:
            logical[-1] = f"{logical[-1]}\n{s}"
    return logical


def _split_md_table(content: str) -> tuple[str, list[str]]:
    """将 markdown 表格拆分为 (表头块, 数据行列表)

    先重组逻辑行, 再拆分: 表头块 = 首行 + |---| 分隔行(存在时),
    其余行视为数据行; 无分隔行时首行视为表头。
    """
    lines = _merge_logical_rows((content or "").splitlines())
    if not lines:
        return "", []
    sep_idx = next(
        (i for i in range(1, min(len(lines), 3)) if _is_md_separator(lines[i])), None
    )
    if sep_idx is not None:
        return "\n".join(lines[: sep_idx + 1]), lines[sep_idx + 1 :]
    return lines[0], lines[1:]


@register_chunker("ragflow", ChunkStrategyEnum.TABLES)
class RAGFlowTableChunker(BaseChunker):
    """RAGFlow 风格表格分块器

    处理逻辑:
    1. TABLE_SHEET: 记录当前 Sheet 名称作为上下文, 不产生独立分块
    2. TABLE (完整表格): 拆出表头块后逐行填充, 每块以 Sheet+表头开头
    3. TABLE_HEADER + TABLE_CONTENT: 表头注入到每个内容块, 内容逐行填充
    4. TEXT/IMAGE_CONTENT: 使用 naive_merge 合并
    5. 保持原始文档顺序
    """

    def chunk(self, chunks: list[Chunk]) -> list[ChunkedItem]:
        if not chunks:
            return []

        results: list[ChunkedItem] = []
        pending_merge: list[Chunk] = []
        current_sheet: str = ""
        current_header: str = ""

        def _flush_merge() -> None:
            nonlocal pending_merge
            if pending_merge:
                merged = naive_merge(
                    pending_merge,
                    chunk_token_num=self.config.chunk_token_num,
                    delimiter=self.config.delimiter,
                    overlapped_percent=self.config.overlapped_percent,
                )
                results.extend(merged)
                pending_merge = []

        for chunk in chunks:
            content = (chunk.content or "").strip()
            if not content:
                continue

            ct = chunk.content_type

            if ct == ContentType.TABLE_SHEET:
                _flush_merge()
                # 解析层输出 "## Sheet名", 剥离 markdown 标题标记
                current_sheet = re.sub(r"^#{1,6}\s*", "", content).strip()
                current_header = ""
                continue

            if ct == ContentType.TABLE_HEADER:
                _flush_merge()
                current_header = content
                continue

            if ct == ContentType.TABLE:
                _flush_merge()
                results.extend(self._process_table(chunk, current_sheet))
                continue

            if ct == ContentType.TABLE_CONTENT:
                _flush_merge()
                results.extend(
                    self._process_table_content(chunk, current_sheet, current_header)
                )
                continue

            if ct in _MERGEABLE_TYPES:
                pending_merge.append(chunk)
                continue

            _flush_merge()
            results.append(self._chunk_to_item(chunk))

        _flush_merge()

        return results

    def _process_table(self, chunk: Chunk, sheet: str) -> list[ChunkedItem]:
        """处理完整表格: 拆出表头块后逐行填充分块"""
        content = (chunk.content or "").strip()
        if not content:
            return []
        header_block, rows = _split_md_table(content)
        return self._pack_rows(rows, header_block, sheet, [chunk])

    def _process_table_content(
        self, chunk: Chunk, sheet: str, header: str
    ) -> list[ChunkedItem]:
        """处理大表格内容块: 以 TABLE_HEADER 为表头, 按逻辑行逐行填充分块"""
        content = (chunk.content or "").strip()
        if not content:
            return []
        rows = _merge_logical_rows(content.splitlines())
        return self._pack_rows(rows, (header or "").strip(), sheet, [chunk])

    # bbox 按行切分

    @staticmethod
    def _source_bbox(sources: list[Chunk]) -> list[float] | None:
        """取来源 Chunk 的整表 bbox (PDF/DOCX 有, XLSX 无则 None)"""
        for s in sources:
            bbox = s.position.bbox if s.position else None
            if bbox and len(bbox) == 4 and bbox[3] != bbox[1]:
                return bbox
        return None

    def _compute_row_bands(
        self, rows: list[str], header_block: str, sources: list[Chunk]
    ) -> list[list[float]] | None:
        """将整表 bbox 竖切为每行条带 [l, top, r, bottom]

        行高按 token 权重估计: 多行单元格(技术规格列)实际占据的视觉高度
        与其 token 数大致成正比, 比等高分更贴近真实行高。
        表头占据条带起始段(权重=表头 token 数), 数据行依次向下排布;
        坐标系方向(PDF 原点左下 t>b / 屏幕坐标 t<b)由线性插值自然兼容。
        无 bbox(XLSX)时返回 None, 各块保留原始 position。
        """
        bbox = self._source_bbox(sources)
        if not bbox:
            return None
        l, t, r, b = bbox
        header_weight = count_tokens(header_block) if header_block else 0
        weights = [max(count_tokens(row), 1) for row in rows]
        total = header_weight + sum(weights)
        if total <= 0:
            return None
        height = b - t
        bands: list[list[float]] = []
        cum = header_weight
        for w in weights:
            top = t + height * cum / total
            cum += w
            bands.append([l, top, r, t + height * cum / total])
        return bands

    @staticmethod
    def _split_band_by_weights(
        band: list[float] | None, weights: list[int]
    ) -> list[list[float] | None]:
        """将单行条带按子块 token 权重比例竖切 (用于超限行拆分后的子块)"""
        if band is None:
            return [None] * len(weights)
        if not weights:
            return []
        l, t, r, b = band
        total = sum(weights) or 1
        bands: list[list[float]] = []
        cum = 0
        for w in weights:
            top = t + (b - t) * cum / total
            cum += w
            bands.append([l, top, r, t + (b - t) * cum / total])
        return bands

    @staticmethod
    def _union_bands(bands: list[list[float]]) -> list[float] | None:
        """连续行条带的外接 bbox: 块内行为连续区间, 取首行 top 到末行 bottom"""
        if not bands:
            return None
        first, last = bands[0], bands[-1]
        return [first[0], first[1], last[2], last[3]]

    def _pack_rows(
        self,
        rows: list[str],
        header_block: str,
        sheet: str,
        sources: list[Chunk],
        bands: list[list[float]] | None = None,
    ) -> list[ChunkedItem]:
        """逐行填充分块: 每块以 [所属工作表]+表头 开头, 达到 token 上限开启下一块

        每块 position.bbox 按其包含的行条带外接计算(无 bbox 来源时保留原 position)。

        单行超限时:
        - split_oversized_row_by_cell=True (默认): 将该行最大单元格一分为二
          拆成两行(其余单元格保留), 递归处理直至每行不超限, 保持表格结构。
          此模式不应用 overlapped_percent(每块均携带表头且行完整, 无需重叠)
        - split_oversized_row_by_cell=False: 直接按 token 硬切成多个独立块,
          此模式 overlapped_percent 生效(下一块头部携带上一块尾部文本)
        """
        limit = max(int(self.config.chunk_token_num or 1), 1)
        # overlap 仅在硬切模式下生效
        if self.config.split_oversized_row_by_cell:
            overlap = 0
        else:
            overlap = max(0, min(int(self.config.overlapped_percent or 0), 99))
        prefix_parts = []
        if sheet:
            prefix_parts.append(f"[所属工作表: {sheet}]")
        if header_block:
            prefix_parts.append(header_block)
        prefix = "\n".join(prefix_parts)

        # 每行条带 bbox: 外部传入(超限行拆分后的子行)或按 token 权重竖切整表 bbox
        if bands is None:
            bands = self._compute_row_bands(rows, header_block, sources)
        if bands is None:
            bands = [None] * len(rows)

        items: list[ChunkedItem] = []
        current_rows: list[str] = []
        current_bands: list[list[float]] = []
        current_tokens = 0

        def _finalize() -> None:
            nonlocal current_rows, current_bands, current_tokens
            if not current_rows:
                return
            body = "\n".join(current_rows)
            content = f"{prefix}\n{body}" if prefix else body
            items.append(
                self._build_table_item(content, sheet, sources, self._union_bands(current_bands))
            )
            # overlap: 从当前块尾部截取文本注入下一块头部 (参考 naive_merge)
            if overlap > 0:
                tail_text = current_rows[-1]
                overlap_len = int(len(tail_text) * overlap / 100)
                if overlap_len > 0:
                    overlap_part = tail_text[-overlap_len:]
                    if overlap_part.strip():
                        current_rows = [overlap_part]
                        # 重叠片段归属上一块末行, 沿用其条带
                        current_bands = [current_bands[-1]] if current_bands else []
                        current_tokens = count_tokens(overlap_part)
                        return
            current_rows = []
            current_bands = []
            current_tokens = 0

        for row, band in zip(rows, bands):
            row_tokens = count_tokens(row)
            if row_tokens > limit:
                # 单行超限: 先封存当前块, 再单独处理该行
                _finalize()
                sub_rows: list[str] = []
                if self.config.split_oversized_row_by_cell:
                    split = self._split_oversized_row(row, limit)
                    if len(split) > 1:
                        sub_rows = split
                if sub_rows:
                    # 子行条带 = 该行条带按子行 token 权重比例竖切
                    sub_bands = self._split_band_by_weights(
                        band, [count_tokens(r) for r in sub_rows]
                    )
                    items.extend(
                        self._pack_rows(sub_rows, header_block, sheet, sources, sub_bands)
                    )
                else:
                    # 直接拆分成多块: 按 token 硬切为独立块, 块间附带 overlap
                    hard_limit = int(limit * 1.5)
                    parts = [
                        p for p in hard_split_by_token_limit(row, limit, hard_limit)
                        if p.strip()
                    ]
                    part_bands = self._split_band_by_weights(
                        band, [count_tokens(p) for p in parts]
                    )
                    prev_tail = ""
                    for part, pband in zip(parts, part_bands):
                        content = f"{prev_tail}{part}" if prev_tail else part
                        items.append(self._build_table_item(content, sheet, sources, pband))
                        overlap_len = int(len(part) * overlap / 100)
                        prev_tail = part[-overlap_len:] if overlap_len > 0 else ""
                continue
            if current_rows and current_tokens + row_tokens > limit:
                _finalize()
            current_rows.append(row)
            if band is not None:
                current_bands.append(band)
            elif current_bands:
                # 混合场景(理论不出现): 沿用前一行条带兜底
                current_bands.append(current_bands[-1])
            current_tokens += row_tokens

        _finalize()

        # 仅有表头无数据行: 表头本身作为一块, 避免内容丢失
        if not items and prefix:
            items.append(self._build_table_item(prefix, sheet, sources))
        return items

    def _split_oversized_row(self, row: str, limit: int) -> list[str]:
        """将超限行按最大单元格一分为二拆成两行, 递归至每行不超限

        无法拆分(单格行/单元格文本不可对半)时返回 [row] 原样,
        由调用方走 token 硬切兜底。
        """
        cells = _parse_md_row(row)
        if len(cells) <= 1:
            return [row]
        idx = max(range(len(cells)), key=lambda i: count_tokens(cells[i]))
        left, right = _split_text_halves(cells[idx])
        if not left or not right:
            return [row]
        halves = [
            _render_md_row(cells[:idx] + [left] + cells[idx + 1 :]),
            _render_md_row(cells[:idx] + [right] + cells[idx + 1 :]),
        ]
        result: list[str] = []
        for half in halves:
            if count_tokens(half) > limit:
                result.extend(self._split_oversized_row(half, limit))
            else:
                result.append(half)
        return result

    def _build_table_item(
        self,
        content: str,
        sheet: str,
        sources: list[Chunk],
        bbox: list[float] | None = None,
    ) -> ChunkedItem:
        """构建表格分块项; bbox 非空时覆盖按行条带计算的 bbox, 否则保留来源位置"""
        item = build_item(content, sources)
        if bbox:
            position = item.position.model_copy()
            position.bbox = bbox
            item.position = position
        if sheet:
            item.metadata = {**(item.metadata or {}), "sheet": sheet}
        return item

    def _chunk_to_item(self, chunk: Chunk) -> ChunkedItem:
        return ChunkedItem(
            content=(chunk.content or "").strip(),
            content_types=[chunk.content_type.value] if chunk.content_type else [],
            position=chunk.position,
            source=chunk.metadata.get("source", "") if chunk.metadata else "",
            metadata=chunk.metadata,
        )
