"""Excel 文档解析器(docling 引擎，支持 .xlsx)。"""

from docling_core.types.doc import GroupItem, GroupLabel

from module_office.utils.file_parase.do.chunk import Chunk, ContentType
from module_office.utils.file_parase.docling.base import DoclingBaseParser


class XlsxParser(DoclingBaseParser):
    """Excel 文档解析器(docling 引擎，支持 .xlsx)。"""

    def _build_group_chunk(self, item: GroupItem, doc, chunk: Chunk) -> list[Chunk]:
        """sheet 页: 有内容时输出二级标题 chunk，标记 heading_level=1。

        sheet 是 xlsx 特有的顶级容器，相当于文档的一级章节，故 heading_level=1。
        其他 group(list/inline 等)跳过。
        """
        if item.label == GroupLabel.SHEET and item.children:
            chunk.content = f"## {item.name}"
            chunk.content_type = ContentType.TABLE_SHEET
            chunk.position.heading_level = 1
            self._mark_unmergeable(chunk)
            return [chunk]
        return []
