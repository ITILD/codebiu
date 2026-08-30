from abc import ABC, abstractmethod
from pathlib import Path

from module_office.utils.file_parase.do.chunk import Chunk


class BaseParser(ABC):
    """解析器基类

    所有文件解析器需继承此类并实现 extract 方法，
    统一输出 do.chunk.Chunk 列表，便于后续扩展 mineru 等其他引擎或自定义解析器。
    """

    @abstractmethod
    async def extract(self, file: Path) -> list[Chunk]:
        """将文件解析为 Chunk 列表

        :param file: 文件路径
        :return: 带元数据(内容类型、位置等)的 Chunk 列表
        """
        raise NotImplementedError
