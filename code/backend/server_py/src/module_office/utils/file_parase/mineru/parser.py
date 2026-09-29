"""MinerU 引擎解析器: 调用远程/本地 MinerU 服务, content_list.json → Chunk。

MinerU 结果 zip 内含 ``{文件名}/content_list.json``(结构化内容列表)、
``{文件名}/full.md``、``{文件名}/images/*``。本解析器按 content_list 逐条映射:

- text          → TEXT; 有 text_level 时 → TITLE(带 heading_level)
- table         → TABLE(table_body html 转紧凑 markdown); 大表拆 TABLE_HEADER+TABLE_CONTENT
- image         → IMAGE(本地落盘文件链接) + IMAGE_CONTENT(caption 优先, 缺省 VLM OCR)
- equation      → TEXT(LaTeX 原文)
- page_idx(0-based) → position.page(1-based, 与 docling 引擎对齐)
"""
import json
import logging
import zipfile
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from PIL import Image

from common.config.path import DIR_TEMP
from common.utils.media.FileFormat import base64_to_url, pil_to_base64
from module_office.dao.doc_extractor_prompt import OCR_SYSTEM_PROMPT
from module_office.utils.file_parase.base import BaseParser
from module_office.utils.file_parase.do.chunk import Chunk, ContentType, Position
from module_office.utils.file_parase.mineru.client import BaseMinerUClient, MinerUError, build_client
from module_office.utils.file_parase.mineru.config import load_config

logger = logging.getLogger(__name__)

# 大表格阈值(字符数): 与 docling 引擎一致, 超过则拆分表头+表内容两个 chunk
_TABLE_LARGE_THRESHOLD = 2000


class MinerUParser(BaseParser):
    """MinerU 引擎解析器(远程 mineru.net / 本地 docker 双支持)。

    构造协议与 docling 引擎一致(``__init__(ocr_llm=None)``), 供 ParserFactory
    统一实例化; ``ocr_llm`` 仅用于图片内容提取(IMAGE_CONTENT), 不参与服务调用。
    """

    def __init__(self, ocr_llm=None):
        self.ocr_llm: BaseChatModel = ocr_llm
        self._client: BaseMinerUClient = build_client(load_config())

    async def extract(self, file: Path) -> list[Chunk]:
        """解析文件: 调用 MinerU 服务获取结果 zip, 解包后逐条转 Chunk。"""
        zip_bytes = await self._client.parse(file)
        content_list, images = self._unpack(zip_bytes, file.stem)

        chunks: list[Chunk] = []
        for item in content_list:
            chunks.extend(await self._item_to_chunks(item, images))
        return chunks

    # 结果解包
    def _unpack(self, zip_bytes: bytes, stem: str) -> tuple[list[dict], dict[str, str]]:
        """解包结果 zip。

        :return: (content_list 条目列表, img_path → 本地落盘路径映射)
        :raises MinerUError: zip 内无 content_list.json 且无 full.md 可回退
        """
        media_dir = DIR_TEMP / stem
        content_list: list[dict] = []
        full_md = ""
        # 双映射: 完整相对键(images/xxx.jpg) 与 文件名 兜底匹配
        images_by_key: dict[str, str] = {}
        images_by_name: dict[str, str] = {}

        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                base = name.rsplit("/", 1)[-1]
                if base == "content_list.json":
                    loaded = json.loads(zf.read(name).decode("utf-8"))
                    if isinstance(loaded, list):
                        content_list = loaded
                elif base == "full.md" and not full_md:
                    full_md = zf.read(name).decode("utf-8", errors="replace")
                elif "/images/" in name and base:
                    media_dir.mkdir(parents=True, exist_ok=True)
                    target = media_dir / base
                    target.write_bytes(zf.read(name))
                    key = name.split("/images/", 1)[1]
                    images_by_key[key] = str(target)
                    images_by_name[base] = str(target)

        if not content_list and full_md:
            # 回退: 无结构化列表时按行粗分 full.md
            logger.warning("MinerU 结果缺少 content_list.json, 回退 full.md 按行分块")
            content_list = [
                {"type": "text", "text": line} for line in full_md.splitlines() if line.strip()
            ]
        if not content_list:
            raise MinerUError("MinerU 结果中无 content_list.json 与 full.md")

        images = images_by_key | images_by_name
        return content_list, images

    # 条目 → Chunk
    async def _item_to_chunks(self, item: dict, images: dict[str, str]) -> list[Chunk]:
        """将单个 content_list 条目映射为 Chunk 列表。"""
        typ = str(item.get("type", ""))
        page = self._page_no(item)
        if typ == "text":
            return self._text_chunks(item, page)
        if typ == "equation":
            text = self._clean(item.get("text"))
            if not text:
                return []
            return [Chunk(content=text, position=Position(page=page), metadata={"mergeable": "false"})]
        if typ == "table":
            return self._table_chunks(item, page)
        if typ == "image":
            return await self._image_chunks(item, page, images)
        # 未知类型: 有文本则按普通文本输出, 保证内容不丢
        text = self._clean(item.get("text"))
        if not text:
            return []
        return [Chunk(content=text, position=Position(page=page))]

    def _text_chunks(self, item: dict, page: int) -> list[Chunk]:
        """文本条目: 有 text_level(标题级别) → TITLE, 否则 TEXT。"""
        text = self._clean(item.get("text"))
        if not text:
            return []
        level = item.get("text_level")
        if level:
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = None
        if level and level > 0:
            return [
                Chunk(
                    content=text,
                    content_type=ContentType.TITLE,
                    position=Position(page=page, heading_level=level),
                )
            ]
        return [Chunk(content=text, position=Position(page=page))]

    def _table_chunks(self, item: dict, page: int) -> list[Chunk]:
        """表格条目: table_body(html) 转紧凑 markdown; 超阈值拆表头+表内容。"""
        caption = self._join_texts(item.get("table_caption"))
        rows = self._html_table_to_rows(str(item.get("table_body") or ""))
        if not rows:
            # 无结构化表格体: caption 兜底输出
            if not caption:
                return []
            return [
                Chunk(
                    content=caption,
                    content_type=ContentType.TABLE,
                    position=Position(page=page),
                    metadata={"mergeable": "false"},
                )
            ]
        pos = Position(page=page)
        prefix = f"{caption}\n\n" if caption else ""
        text_len = sum(len(c) for r in rows for c in r)

        header_md = self._rows_to_md_table([rows[0]], with_separator=True)
        if text_len <= _TABLE_LARGE_THRESHOLD or len(rows) == 1:
            body_md = self._rows_to_md_table(rows[1:], with_separator=False)
            md = prefix + header_md + (f"\n{body_md}" if body_md else "")
            return [
                Chunk(
                    content=md,
                    content_type=ContentType.TABLE,
                    position=pos,
                    metadata={"mergeable": "false"},
                )
            ]
        # 大表格: 拆 TABLE_HEADER + TABLE_CONTENT(与 docling 引擎一致)
        body_md = self._rows_to_md_table(rows[1:], with_separator=False)
        return [
            Chunk(
                content=prefix + header_md,
                content_type=ContentType.TABLE_HEADER,
                position=pos,
                metadata={"mergeable": "false"},
            ),
            Chunk(
                content=body_md,
                content_type=ContentType.TABLE_CONTENT,
                position=pos,
                metadata={"mergeable": "false"},
            ),
        ]

    async def _image_chunks(self, item: dict, page: int, images: dict[str, str]) -> list[Chunk]:
        """图片条目: IMAGE(文件链接) + IMAGE_CONTENT(caption 优先, 缺省 VLM OCR)。"""
        img_path = str(item.get("img_path") or "")
        local_path = images.get(img_path) or images.get(Path(img_path).name)
        caption = self._join_texts(item.get("img_caption"))
        result: list[Chunk] = []
        meta = {"image_path": local_path} if local_path else None

        if local_path:
            result.append(
                Chunk(
                    content=f"![]({local_path})",
                    content_type=ContentType.IMAGE,
                    position=Position(page=page),
                    metadata={**(meta or {}), "mergeable": "false"},
                )
            )

        content_text = caption
        if not content_text and self.ocr_llm and local_path:
            content_text = await self._ocr_image(local_path)
        if content_text:
            result.append(
                Chunk(
                    content=content_text,
                    content_type=ContentType.IMAGE_CONTENT,
                    position=Position(page=page),
                    metadata={**(meta or {}), "mergeable": "false"},
                )
            )
        return result

    async def _ocr_image(self, img_path: str) -> str:
        """用 ocr_llm(VLM) 提取图片内容, 失败返回空串。逻辑与 docling 引擎一致。"""
        try:
            with Image.open(img_path) as pil_img:
                img_base64 = pil_to_base64(pil_img)
            image_url = base64_to_url(img_base64)
            messages = [
                SystemMessage(content=OCR_SYSTEM_PROMPT),
                HumanMessage(
                    content=[{"type": "image_url", "image_url": {"url": image_url}}]
                ),
            ]
            response = await self.ocr_llm.ainvoke(messages)
            return response.content.strip()
        except Exception as e:
            logger.error("VLM 图片内容提取失败: %s", e)
            return ""

    # 工具方法
    @staticmethod
    def _page_no(item: dict) -> int:
        """page_idx(0-based) → 页码(1-based, 与 docling prov.page_no 对齐)。"""
        try:
            return int(item.get("page_idx") or 0) + 1
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _clean(value) -> str:
        """清洗文本: 去首尾空白, 非字符串安全转空。"""
        return str(value).strip() if isinstance(value, str) else ""

    @staticmethod
    def _join_texts(value) -> str:
        """caption 等字段兼容 str / list[str] 两种形态, 拼接为多行文本。"""
        if not value:
            return ""
        if isinstance(value, str):
            return value.strip()
        return "\n".join(str(v).strip() for v in value if str(v).strip())

    @staticmethod
    def _html_table_to_rows(html: str) -> list[list[str]]:
        """解析 table_body html 为二维文本网格: colspan 展开保持列对齐, 行宽补齐。"""
        if not html.strip():
            return []
        soup = BeautifulSoup(html, "lxml")
        rows: list[list[str]] = []
        for tr in soup.find_all("tr"):
            cells: list[str] = []
            for cell in tr.find_all(["td", "th"]):
                text = cell.get_text(" ", strip=True)
                try:
                    colspan = max(int(cell.get("colspan", 1) or 1), 1)
                except (TypeError, ValueError):
                    colspan = 1
                cells.append(text)
                cells.extend([""] * (colspan - 1))
            if cells:
                rows.append(cells)
        if not rows:
            return []
        width = max(len(r) for r in rows)
        return [r + [""] * (width - len(r)) for r in rows]

    @staticmethod
    def _rows_to_md_table(rows: list[list[str]], *, with_separator: bool) -> str:
        """渲染紧凑 markdown 表格(与 docling 引擎一致的分隔符与转义风格)。"""
        if not rows:
            return ""
        lines: list[str] = []
        for i, row in enumerate(rows):
            cells = [c.replace("|", "\\|") for c in row]
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0 and with_separator:
                lines.append("|" + "|".join("---" for _ in row) + "|")
        return "\n".join(lines)
