from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_site.do.blog import BlogPost, BlogPostCreate, BlogPostUpdate, PostStatus
from module_site.dao.blog import BlogPostDao


class BlogPostService:
    """博客文章服务: 发布(在线 markdown/关联 URL)、管理与展示"""

    def __init__(self, blog_post_dao: BlogPostDao):
        """依赖注入构造器: 初始化所需的数据访问对象"""
        self.blog_post_dao = blog_post_dao

    async def add(self, post: BlogPostCreate, user_id: str) -> str:
        """新增文章(归属当前用户)
        :return: 新建文章ID
        """
        return await self.blog_post_dao.add(post, user_id)

    async def get_visible(self, post_id: str, user_id: str) -> BlogPost | None:
        """查询单篇文章(带可见性判定)
        已发布文章对持有 read 权限的用户可见; 草稿仅作者可见
        :param user_id: 请求者用户ID
        """
        result = await self.blog_post_dao.get(post_id)
        if not result:
            return None
        if result.user_id != user_id and result.status != PostStatus.Published:
            return None
        return result

    async def update(self, post_id: str, post: BlogPostUpdate, user_id: str) -> None:
        """更新本人文章"""
        await self.blog_post_dao.update(post_id, post, user_id)

    async def delete(self, post_id: str, user_id: str) -> None:
        """删除本人文章"""
        await self.blog_post_dao.delete(post_id, user_id)

    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        title: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> PaginationResponse:
        """分页获取本人文章列表(管理页)"""
        items = await self.blog_post_dao.list_mine(
            pagination, user_id, title=title, status=status, source_type=source_type
        )
        total = await self.blog_post_dao.count_mine(
            user_id, title=title, status=status, source_type=source_type
        )
        return PaginationResponse.create(items, total, pagination)

    async def list_published(
        self,
        pagination: PaginationParams,
        keyword: str | None = None,
    ) -> PaginationResponse:
        """分页获取已发布文章列表(展示页)"""
        items = await self.blog_post_dao.list_published(pagination, keyword=keyword)
        total = await self.blog_post_dao.count_published(keyword=keyword)
        return PaginationResponse.create(items, total, pagination)
