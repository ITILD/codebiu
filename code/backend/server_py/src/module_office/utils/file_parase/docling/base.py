"""docling 引擎解析器基类。

封装 docling DocumentConverter 的通用迭代解析逻辑，输出带原始位置信息的 Chunk。
子类可覆盖 ``_get_converter`` 提供格式专用配置(如 PDFParser 的 do_ocr 智能选择)。
"""

import base64
import logging
import os
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from docling.document_converter import DocumentConverter
from docling_core.types.doc import (
    GroupItem,
    InlineGroup,
    ListItem,
    NodeItem,
    PictureItem,
    PictureTabularChartData,
    SectionHeaderItem,
    TableItem,
    TextItem,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image

from common.config.path import DIR_TEMP
from module_office.dao.doc_extractor_prompt import OCR_SYSTEM_PROMPT
from module_office.utils.file_parase.base import BaseParser
from module_office.utils.file_parase.do.chunk import Chunk, ContentType
from common.utils.media.FileFormat import pil_to_base64, base64_to_url

logger = logging.getLogger(__name__)

# bbox 顶部坐标容差(点)，用于判断两个文本块是否在同一行
_INLINE_TOL = 3.0
# 大表格阈值(字符数)：超过则扁平化后拆分为表头+表内容两个 chunk
_TABLE_LARGE_THRESHOLD = 2000

# 禁用 torch.dynamo: 必须在 torch 导入前设环境变量才生效(torch 2.13 的 C 层
# 标志在 torch._dynamo 导入时读取，之后 Python 层 config.disable 无效)。
# transformers 5.x 的 RT-DETR(layout-heron)forward 触发 graph break，每次推理
# 重新追踪致极慢(纯 layout 57s→4.3s，13x 加速)。docling 用 eager 模式，无副作用。
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")


class DoclingBaseParser(BaseParser):
    """docling 引擎解析器基类。

    子类可覆盖 ``_get_converter`` 提供格式专用配置(如 PDFParser 按 PDF 文本层
    选择 do_ocr)；默认返回无自定义 pipeline 的通用 converter，适用于 docx/xlsx 等。

    Converter(持有已加载模型)在**类级别**缓存，跨实例复用避免每次请求重复加载；
    ``ocr_llm`` 是 per-request 的(仅用于图片内容提取，不参与 converter 构建)。
    """

    # 类级通用 converter 缓存: docx/xlsx/pptx/md 等无自定义 pipeline 的格式共用
    _shared_converter: DocumentConverter | None = None

    def __init__(self, ocr_llm=None):
        # ocr_llm 预留给 docling OCR pipeline 配置(如扫描件/图片型 PDF);
        # 仅用于 _extract_image_content, 不参与 converter 创建, 故 per-request 安全
        self.ocr_llm: BaseChatModel = ocr_llm

    def _get_converter(self, file: Path) -> DocumentConverter:
        """返回解析 file 所用的 DocumentConverter。子类可覆盖以按需选择。

        默认返回无自定义 pipeline 的通用 converter(docx/xlsx/pptx/md 等格式适用)。
        converter 在类级别缓存, 跨所有实例复用, 避免重复加载模型。
        """
        if DoclingBaseParser._shared_converter is None:
            DoclingBaseParser._shared_converter = DocumentConverter()
        return DoclingBaseParser._shared_converter

    # 公共接口
    async def extract(self, file: Path) -> list[Chunk]:
        """解析文件，按文档元素顺序生成带位置信息的 Chunk。"""
        doc = self._get_converter(file).convert(file).document

        # 表格子项 self_ref 集合：表格整体已通过 export_to_markdown 输出，
        # 其单元格子项需跳过以避免重复
        table_refs = self._collect_table_descendant_refs(doc)

        # 文件内媒体文件输出目录
        media_dir = DIR_TEMP / f"{file.stem}"
        media_dir.mkdir(parents=True, exist_ok=True)

        # 逐元素构建 chunk(with_groups=True 以遍历 sheet 等容器节点)
        raw_chunks: list[Chunk] = []
        for item, level in doc.iterate_items(with_groups=True):
            if item.self_ref in table_refs:
                continue
            for chunk in await self._build_chunk(item, doc, level, media_dir):
                if chunk.content:
                    raw_chunks.append(chunk)

        # 合并同一行内的多格式文本(docling 会将单行拆成多个 TextItem)
        raw_chunks = self._merge_inline_chunks(raw_chunks)
        # 合并连续的 TABLE chunk (跨页表格被 docling 拆分为多个 TableItem)
        raw_chunks = self._merge_consecutive_tables(raw_chunks)
        return raw_chunks

    # Chunk 构建
    async def _build_chunk(
        self, item: NodeItem, doc, level: int, media_dir: Path
    ) -> list[Chunk]:
        """将单个文档元素转换为 Chunk 列表，填充位置、内容、类型。

        大多数元素返回单个 chunk；大表格(>1000字)扁平化后返回表头+表内容两个 chunk。
        """
        chunk = Chunk()
        chunk.metadata = {}
        self._fill_position(chunk, item)
        self._tag_inline_parent(chunk, item, doc)

        if isinstance(item, GroupItem):
            # GroupItem 处理交由子类 hook(如 xlsx 的 sheet)；默认跳过所有 group
            return self._build_group_chunk(item, doc, chunk)

        if isinstance(item, ListItem):
            # marker 为标题编号；空 marker 且空文本则跳过
            if not item.marker and not item.text:
                return []
            text = self._format_text(item)
            prefix = "#" * level + " " if level > 0 else ""
            chunk.content = f"{prefix}{item.marker or ''}{text or ''}"
            # 有 marker (标题编号) 时为标题类型, 无 marker 时为普通列表项
            if item.marker:
                chunk.content_type = ContentType.TITLE
            self._mark_unmergeable(chunk)

        elif isinstance(item, SectionHeaderItem):
            # 章节标题：记录语义标题级别(h1/h2/h3...)供后续定位原文层级
            if not item.text:
                return []
            chunk.position.heading_level = item.level
            chunk.content_type = ContentType.TITLE
            chunk.content = self._format_text(item)

        elif isinstance(item, TextItem):
            if not item.text:
                return []
            chunk.content = self._format_text(item)

        elif isinstance(item, TableItem):
            return self._build_table_chunks(item, doc, chunk)

        elif isinstance(item, PictureItem):
            return await self._build_picture_chunks(item, doc, chunk, media_dir)

        else:
            if not getattr(item, "text", None):
                return []
            chunk.content = self._format_text(item)
            self._mark_unmergeable(chunk)

        return [chunk]

    def _build_group_chunk(self, item: GroupItem, doc, chunk: Chunk) -> list[Chunk]:
        """处理 GroupItem 容器节点。

        默认跳过所有 group(list/inline/sheet 等)，子类可覆盖以处理特定容器。
        例如 XlsxParser 覆盖此方法将 sheet 页输出为 TABLE_SHEET 标题 chunk。
        """
        return []

    async def _build_picture_chunks(
        self, item: PictureItem, doc, chunk: Chunk, media_dir: Path
    ) -> list[Chunk]:
        """构建图片 chunk。

        - 始终输出 IMAGE chunk(markdown 格式文件链接 ``![](path)``)
        - IMAGE_CONTENT 内容来源(二选一)：
          1. 优先：图片自带结构化表格/图表数据(meta.tabular_chart)，
             直接提取为 markdown 表格，避免冗余 VLM OCR。
          2. 回退：无结构化数据时用 ocr_llm(VLM) 提取。
        """
        # 保存图片
        img_path: str | None = self._save_picture(item, doc, media_dir)
        if img_path:
            chunk.metadata["image_path"] = img_path

        base_meta = dict(chunk.metadata or {})
        base_pos = chunk.position.model_copy()
        result: list[Chunk] = []

        # 1. IMAGE：markdown 格式文件链接(图片保存成功时才输出)
        if img_path:
            link_chunk = Chunk(
                content=f"![]({img_path})",
                content_type=ContentType.IMAGE,
                position=base_pos.model_copy(),
                metadata=dict(base_meta),
            )
            self._mark_unmergeable(link_chunk)
            result.append(link_chunk)

        # 2. IMAGE_CONTENT：优先用结构化图表数据，无则用 VLM 提取
        content_text = self._extract_chart_table_md(item)
        if not content_text and self.ocr_llm:
            pil_img = item.get_image(doc=doc)
            if pil_img is not None:
                content_text = await self._extract_image_content(pil_img)

        if content_text:
            content_chunk = Chunk(
                content=content_text,
                content_type=ContentType.IMAGE_CONTENT,
                position=base_pos.model_copy(),
                metadata=dict(base_meta),
            )
            self._mark_unmergeable(content_chunk)
            result.append(content_chunk)
        return result

    def _extract_chart_table_md(self, item: PictureItem) -> str:
        """从 PictureItem 的结构化图表数据提取紧凑 markdown 表格。

        docling 解析 docx/pptx 等格式时，内嵌图表(如 Excel 图表)的底层数据会
        保存在 ``PictureItem.meta.tabular_chart``(含 ``TableData``)中。
        此方法复用表格渲染逻辑将其转为紧凑 markdown 表格，避免对已有结构化
        数据的图片再做冗余 VLM OCR。

        同时兼容 deprecated ``annotations`` 字段(含 ``PictureTabularChartData``)。
        无结构化数据时返回空串。
        """
        # 优先从 meta.tabular_chart 获取(新 API)
        data = None
        if item.meta and item.meta.tabular_chart:
            data = item.meta.tabular_chart.chart_data
        else:
            # 回退到 deprecated annotations
            for ann in item.annotations:
                if isinstance(ann, PictureTabularChartData):
                    data = ann.chart_data
                    break

        if (
            data is None
            or data.num_rows == 0
            or data.num_cols == 0
            or not data.table_cells
        ):
            return ""

        grid = self._build_compact_grid(data)
        header_idxs = sorted(
            {
                c.start_row_offset_idx
                for c in data.table_cells
                if getattr(c, "column_header", False)
            }
        )
        if not header_idxs:
            header_idxs = [0]
        body_idxs = [i for i in range(data.num_rows) if i not in header_idxs]

        header_md = self._rows_to_md_table(
            [grid[i] for i in header_idxs], with_separator=True
        )
        body_md = self._rows_to_md_table(
            [grid[i] for i in body_idxs], with_separator=False
        )
        return header_md + ("\n" + body_md if body_md else "")

    async def _extract_image_content(self, pil_img: Image.Image) -> str:
        """用 ocr_llm(VLM) 异步提取图片内容，返回文本；失败返回空串。

        用 JPEG quality=85 编码(比 PNG 体积小数倍、base64 传输快)：VLM 输入会
        resize 到固定分辨率，原图超分辨率被丢弃，故 JPEG 有损不影响识别；
        RGBA 先转 RGB(JPEG 不支持 alpha 通道)。
        """
        if not self.ocr_llm:
            return ""
        try:
            img_base64 = pil_to_base64(pil_img)
            image_url = base64_to_url(img_base64)
            messages = [
                SystemMessage(content=OCR_SYSTEM_PROMPT),
                HumanMessage(
                    content=[
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]
                ),
            ]
            response = await self.ocr_llm.ainvoke(messages)
            text = response.content.strip()
            return text
        except Exception as e:
            logger.error("VLM 图片内容提取失败: %s", e)
            return ""

    def _build_table_chunks(self, item: TableItem, doc, chunk: Chunk) -> list[Chunk]:
        """构建表格 chunk：小表格(<=1000字)输出单个 TABLE；大表格扁平化后拆分
        TABLE_HEADER + TABLE_CONTENT 两个 chunk。

        所有表格均通过紧凑二维网格渲染(合并单元格仅起始位置填值、分隔符用最小
        ``|---|``、无空格填充)，避免 ``export_to_markdown`` 的空格填充和
        ``---`` 膨胀。无结构化数据时回退到 ``export_to_markdown``。
        """
        data = getattr(item, "data", None)
        # 无结构化数据时回退到 export_to_markdown
        if (
            data is None
            or data.num_rows == 0
            or data.num_cols == 0
            or not data.table_cells
        ):
            md = item.export_to_markdown(doc).strip()
            if not md:
                return []
            chunk.content_type = ContentType.TABLE
            chunk.content = md
            self._mark_unmergeable(chunk)
            return [chunk]

        # 实际文本字数(markdown 格式字符不计入：|、---、空格填充、合并单元格
        # 展开重复会大幅膨胀 markdown 长度，不能代表真实内容量)
        text_len = sum(len(c.text or "") for c in data.table_cells)

        # 紧凑二维网格 + 表头行识别
        grid = self._build_compact_grid(data)
        header_idxs = sorted(
            {
                c.start_row_offset_idx
                for c in data.table_cells
                if getattr(c, "column_header", False)
            }
        )
        if not header_idxs:
            header_idxs = [0]
        body_idxs = [i for i in range(data.num_rows) if i not in header_idxs]

        header_md = self._rows_to_md_table(
            [grid[i] for i in header_idxs], with_separator=True
        )

        if text_len <= _TABLE_LARGE_THRESHOLD or not body_idxs:
            # 小表格(或仅有表头)：单个 TABLE chunk
            body_md = self._rows_to_md_table(
                [grid[i] for i in body_idxs], with_separator=False
            )
            md = header_md + ("\n" + body_md if body_md else "")
            chunk.content_type = ContentType.TABLE
            chunk.content = md
            self._mark_unmergeable(chunk)
            return [chunk]

        # 大表格：拆分 TABLE_HEADER + TABLE_CONTENT
        body_md = self._rows_to_md_table(
            [grid[i] for i in body_idxs], with_separator=False
        )
        base_meta = dict(chunk.metadata or {})
        base_meta["mergeable"] = "false"
        return [
            Chunk(
                content=header_md,
                content_type=ContentType.TABLE_HEADER,
                position=chunk.position.model_copy(),
                metadata=dict(base_meta),
            ),
            Chunk(
                content=body_md,
                content_type=ContentType.TABLE_CONTENT,
                position=chunk.position.model_copy(),
                metadata=dict(base_meta),
            ),
        ]

    @staticmethod
    def _build_compact_grid(data) -> list[list[str]]:
        """构建紧凑二维网格：合并单元格仅在起始位置填值，跨域其余位置置空。

        相比 ``TableData.grid``(合并单元格在各跨域位置重复填值)，此方法避免
        无意义的重复，大幅削减复杂表格的 markdown 字符数。
        """
        grid = [[""] * data.num_cols for _ in range(data.num_rows)]
        for cell in data.table_cells:
            r = cell.start_row_offset_idx
            c = cell.start_col_offset_idx
            if 0 <= r < data.num_rows and 0 <= c < data.num_cols:
                grid[r][c] = cell.text or ""
        return grid

    @staticmethod
    def _rows_to_md_table(rows: list[list[str]], *, with_separator: bool) -> str:
        """将二维字符串列表渲染为紧凑 markdown 表格行。

        with_separator=True 时在首行后插入 ``|---|`` 分隔行(用于表头)。
        """
        if not rows:
            return ""
        lines: list[str] = []
        for i, row in enumerate(rows):
            cells = [c.replace("|", "\\|") for c in row]
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0 and with_separator:
                lines.append("|" + "|".join("---" for _ in row) + "|")
        return "\n".join(lines)

    def _format_text(self, item: TextItem | ListItem) -> str:
        """应用斜体/下划线/删除线格式标记。"""
        text = item.text
        fmt = getattr(item, "formatting", None)
        if not fmt:
            return text
        if fmt.italic:
            text = f"*{text}*"
        if fmt.underline:
            text = f"<u>{text}</u>"
        if fmt.strikethrough:
            text = f"~~{text}~~"
        return text

    def _save_picture(self, item: PictureItem, doc, media_dir: Path) -> str | None:
        """将图片保存到 DIR_TEMP，返回路径；失败返回 ``<!-- ... -->`` 占位符。"""
        try:
            pil_image = item.get_image(doc=doc)
            if pil_image is None:
                return
            img_path = media_dir / f"{uuid4().hex}.png"
            pil_image.save(img_path, format="PNG")
            return str(img_path)
        except (OSError, ValueError, RuntimeError) as e:
            return

    # 元数据填充
    def _fill_position(self, chunk: Chunk, item: NodeItem) -> None:
        """从 item.prov 提取页码与 bbox，写入 chunk 位置。"""
        provs = getattr(item, "prov", None)
        if not provs:
            return
        prov = provs[0]
        chunk.position.page = prov.page_no
        bbox = getattr(prov, "bbox", None)
        if bbox:
            chunk.position.bbox = [bbox.l, bbox.t, bbox.r, bbox.b]

    def _tag_inline_parent(self, chunk: Chunk, item: NodeItem, doc) -> None:
        """若 item 位于 InlineGroup 内，记录父节点 ref 供行内合并使用。"""
        parent_ref = getattr(item, "parent", None)
        if parent_ref is None:
            return
        try:
            parent = parent_ref.resolve(doc)
        except (RuntimeError, AttributeError, IndexError, ValueError):
            return
        if isinstance(parent, InlineGroup):
            chunk.metadata["inline_parent"] = parent.self_ref

    def _mark_unmergeable(self, chunk: Chunk) -> None:
        """标记 chunk 不参与行内合并(列表项/表格/图片等)。"""
        chunk.metadata["mergeable"] = "false"

    # 行内合并
    def _merge_inline_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """合并同一行内的文本 chunk，避免单行多格式文本被拆成多行。

        优先按 InlineGroup 父节点合并(docx 等无 bbox 的文档)，
        回退到 bbox 顶部坐标合并(pdf 等有 prov 的文档)。
        """
        if not chunks:
            return chunks
        result: list[Chunk] = []
        current = chunks[0]
        for nxt in chunks[1:]:
            sep = self._inline_separator(current, nxt)
            if sep is not None:
                current.content = (current.content or "") + sep + (nxt.content or "")
                self._extend_bbox(current, nxt)
            else:
                result.append(current)
                current = nxt
        result.append(current)
        return result

    def _inline_separator(self, a: Chunk, b: Chunk) -> str | None:
        """判断 b 是否是 a 的行内延续，返回拼接分隔符；否则 None。"""
        # 仅纯文本可合并
        if a.content_type != ContentType.TEXT or b.content_type != ContentType.TEXT:
            return None
        if (
            a.metadata.get("mergeable") == "false"
            or b.metadata.get("mergeable") == "false"
        ):
            return None
        # 优先：同一 InlineGroup 内(空格分隔，与 MarkdownDocSerializer 一致)
        a_parent = a.metadata.get("inline_parent")
        b_parent = b.metadata.get("inline_parent")
        if a_parent and b_parent and a_parent == b_parent:
            return " "
        # 回退：bbox 同行判断(均无 InlineGroup 时)
        if a_parent is None and b_parent is None:
            if a.position.page != b.position.page:
                return None
            a_bbox = a.position.bbox
            b_bbox = b.position.bbox
            if a_bbox and b_bbox and abs(a_bbox[1] - b_bbox[1]) <= _INLINE_TOL:
                return ""  # 空间相邻，直接拼接
        return None

    def _extend_bbox(self, a: Chunk, b: Chunk) -> None:
        """合并后扩展 bbox 右边界。"""
        if not a.position.bbox or not b.position.bbox:
            return
        a.position.bbox[2] = max(a.position.bbox[2], b.position.bbox[2])

    def _merge_consecutive_tables(self, chunks: list[Chunk]) -> list[Chunk]:
        """合并连续的 TABLE chunk。

        docling 可能把跨页表格拆分为多个 TableItem (每页一个),
        此方法将相邻的 TABLE chunk 合并回一个, 内容用换行连接。
        """
        if not chunks:
            return chunks
        result: list[Chunk] = []
        current = chunks[0]
        for nxt in chunks[1:]:
            if (
                current.content_type == ContentType.TABLE
                and nxt.content_type == ContentType.TABLE
            ):
                current.content = (current.content or "") + "\n" + (nxt.content or "")
            else:
                result.append(current)
                current = nxt
        result.append(current)
        return result

    # 表格子项收集

    def _collect_table_descendant_refs(self, doc) -> set[str]:
        """收集所有 TableItem 后代的 self_ref，用于跳过表格内部子项。"""
        refs: set[str] = set()
        for table in doc.tables:
            self._collect_descendants(doc, table, refs)
        return refs

    def _collect_descendants(self, doc, item: NodeItem, acc: set[str]) -> None:
        """递归收集 item 的所有后代 self_ref。"""
        for child_ref in getattr(item, "children", None) or []:
            if child_ref.cref in acc:
                continue
            acc.add(child_ref.cref)
            child = child_ref.resolve(doc)
            if isinstance(child, NodeItem):
                self._collect_descendants(doc, child, acc)
