from pathlib import Path
from typing import ClassVar

from module_office.utils.file_parase.base import BaseParser
from module_office.utils.file_parase.code.parser import CodeParser
from module_office.utils.file_parase.docling.parsers import (
    MarkdownParser,
    PDFParser,
    PptxParser,
    WordParser,
    XlsxParser,
)


class ParserFactory:
    """解析器工厂

    根据文件后缀创建对应解析器实例，统一输出 do.chunk.Chunk 列表。

    扩展方式：
      - 新增文件格式：在对应引擎目录下新增解析器类(继承该引擎 base)，
        并在下方注册表中登记 后缀 -> 解析器类。
      - 新增解析引擎(如 mineru)：在 file_parase 下新建引擎目录实现 BaseParser 子类，
        新增该引擎的注册表与 engine 分支。
    """

    # docling 引擎: 后缀 -> 解析器类
    _DOCLING_REGISTRY: ClassVar[dict[str, BaseParser]] = {
        ".pdf": PDFParser,
        ".docx": WordParser,
        ".doc": WordParser,
        ".pptx": PptxParser,
        ".xlsx": XlsxParser,
        ".md": MarkdownParser,
        ".markdown": MarkdownParser,
        ".csv": MarkdownParser,
        ".txt": MarkdownParser,
        ".py": CodeParser,
        ".java": CodeParser,
    }

    @classmethod
    def create(
        cls,
        file: Path,
        *,
        ocr_llm=None,
        engine: str = "docling",
    ) -> BaseParser:
        """创建解析器

        :param file: 文件路径(按后缀路由)
        :param ocr_llm: OCR 模型(用于 PDF 等需要 OCR 的场景)
        :param engine: 解析引擎名称，默认 docling
        :return: BaseParser 实例
        """
        if engine == "docling":
            registry = cls._DOCLING_REGISTRY
        else:
            raise ValueError(f"不支持的解析引擎: {engine}")

        suffix = file.suffix.lower()
        parser_cls = registry.get(suffix)
        if parser_cls is None:
            raise ValueError(f"不支持的文件类型: {suffix} (engine={engine})")

        # 所有注册解析器保持统一构造协议，代码解析器会忽略 ocr_llm。
        return parser_cls(ocr_llm=ocr_llm)
