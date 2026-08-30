from fastapi import Depends

from module_websearch.service.websearch import WebSearchService


async def get_websearch_service() -> WebSearchService:
    """网页搜索Service工厂"""
    return WebSearchService()
