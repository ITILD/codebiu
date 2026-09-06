from fastapi import Depends

from module_site.dao.blog import BlogPostDao
from module_site.service.blog import BlogPostService


async def get_blog_post_dao() -> BlogPostDao:
    """DAO工厂"""
    return BlogPostDao()


async def get_blog_post_service(
    dao: BlogPostDao = Depends(get_blog_post_dao),
) -> BlogPostService:
    """Service工厂"""
    return BlogPostService(dao)
