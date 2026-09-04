from pathlib import Path

from langchain_core.language_models import BaseChatModel

from module_office.do.schemas import FileType
from module_office.utils.file_parase.do.chunk import Chunk
from module_office.utils.file_parase.factory import ParserFactory
from module_office.utils.file_parase.base import BaseParser


class DocumentParseService:
    """文件解析服务"""

    def __init__(self):
        """依赖注入构造器:初始化所需的数据访问对象"""
        pass

    async def file2chunk(
        self,
        file_path: Path,
        ocr_llm: BaseChatModel | None = None,
        audio_llm: BaseChatModel | None = None,
        video_llm: BaseChatModel | None = None,
    ) -> list[Chunk]:
        """
        将文件解析为带元数据(文件原位置，文件类型大小等)的Markdown 格式
        :param file_path: 文件路径
        :param ocr_llm: 文档文件ocr识别的模型
        :param audio_llm: 支持音频文件识别的模型
        :param video_llm: 支持视频文件识别的模型
        :return: Markdown 格式文本
        """
        file_chunk: list[Chunk] = []
        ext = file_path.suffix.lower()
        # 当前接入 docling，后续参考 MinerU 接入
        # https://github.com/opendatalab/MinerU/blob/master/mineru/model/docx/main.py
        if FileType.is_document(ext):
            # 文档文件: 通过工厂按后缀路由到对应解析器
            parser: BaseParser = ParserFactory.create(file_path, ocr_llm=ocr_llm)
            file_chunk = await parser.extract(file_path)
        elif FileType.is_image(ext):
            # 图片文件: 待接入图片解析器
            pass
        elif FileType.is_audio(ext):
            # 音频文件: 待接入音频解析器
            pass
        elif FileType.is_video(ext):
            # 视频文件: 待接入视频解析器
            pass
        else:
            raise ValueError(f"不支持的文件类型: {ext}")
        return file_chunk

    async def file2markdown(
        self,
        file_path: Path,
        ocr_llm: BaseChatModel | None = None,
        audio_llm: BaseChatModel | None = None,
        video_llm: BaseChatModel | None = None,
    ) -> str:
        """
        将文件解析为Markdown格式
        """
        chunks = await self.file2chunk(file_path, ocr_llm, audio_llm, video_llm)
        markdown = "\n".join([chunk.content for chunk in chunks])

        return markdown
