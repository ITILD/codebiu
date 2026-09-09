from abc import ABC, abstractmethod

class Rerank(ABC):
    """Interface for rerank models."""
    @abstractmethod
    def rerank(self,query,texts: list[str]) -> list:
        pass
    async def arerank(self,query,documents: list[str]) -> list:
        pass
