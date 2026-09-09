from abc import ABC, abstractmethod


class Rerank(ABC):
    """重排序(Rerank)模型抽象接口"""

    @abstractmethod
    def rerank(self, query: str, texts: list[str], top_n: int | None = None) -> list:
        """同步文本重排序"""

    @abstractmethod
    async def arerank(self, query: str, documents: list[str], top_n: int | None = None) -> list:
        """异步文本重排序"""
