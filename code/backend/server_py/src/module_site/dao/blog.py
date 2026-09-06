from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_site.do.blog import BlogPost, BlogPostCreate, BlogPostUpdate, PostStatus


class BlogPostDao:
    """博客文章数据访问(全部按 user_id 归属隔离)"""

    @DaoRel
    async def add(
        self, post: BlogPostCreate, user_id: str, session: AsyncSession | None = None
    ) -> str:
        """新增博客文章记录
        :param post: 文章创建数据
        :param user_id: 作者用户ID
        :return: 新创建文章ID
        """
        db_post = BlogPost.model_validate(
            post.model_dump(exclude_unset=True), update={"user_id": user_id}
        )
        session.add(db_post)
        await session.flush()
        return db_post.id

    @DaoRel
    async def get(
        self, post_id: str, session: AsyncSession | None = None
    ) -> BlogPost | None:
        """查询单篇文章(不限归属, 由服务层按展示语义判定可见性)"""
        return await session.get(BlogPost, post_id)

    @DaoRel
    async def update(
        self,
        post_id: str,
        post: BlogPostUpdate,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """直接更新本人文章记录(不先查询)
        :raises: ValueError 文章不存在或不属于当前用户
        """
        update_data = post.model_dump(exclude_unset=True)
        stmt = (
            update(BlogPost)
            .where(BlogPost.id == post_id, BlogPost.user_id == user_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {post_id} 的博客文章")
        await session.flush()

    @DaoRel
    async def delete(
        self, post_id: str, user_id: str, session: AsyncSession | None = None
    ) -> None:
        """删除本人文章
        :raises: ValueError 文章不存在或不属于当前用户
        """
        post = await session.get(BlogPost, post_id)
        if not post or post.user_id != user_id:
            raise ValueError(f"未找到ID为 {post_id} 的博客文章")
        await session.delete(post)
        await session.flush()

    @DaoRel
    async def list_mine(
        self,
        pagination: PaginationParams,
        user_id: str,
        session: AsyncSession | None = None,
        title: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> list[BlogPost]:
        """分页查询本人文章列表(支持标题模糊/状态/来源过滤)"""
        conditions = [BlogPost.user_id == user_id]
        if title:
            conditions.append(BlogPost.title.contains(title))
        if status:
            conditions.append(BlogPost.status == status)
        if source_type:
            conditions.append(BlogPost.source_type == source_type)

        statement = (
            select(BlogPost)
            .where(*conditions)
            .order_by(BlogPost.created_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_mine(
        self,
        user_id: str,
        session: AsyncSession | None = None,
        title: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
    ) -> int:
        """统计本人文章总数(与列表过滤条件一致)"""
        conditions = [BlogPost.user_id == user_id]
        if title:
            conditions.append(BlogPost.title.contains(title))
        if status:
            conditions.append(BlogPost.status == status)
        if source_type:
            conditions.append(BlogPost.source_type == source_type)

        statement = select(func.count()).select_from(BlogPost).where(*conditions)
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def list_published(
        self,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
        keyword: str | None = None,
    ) -> list[BlogPost]:
        """分页查询全部已发布文章(展示页公开内容, 仅返回已发布状态)"""
        conditions = [BlogPost.status == PostStatus.Published]
        if keyword:
            conditions.append(BlogPost.title.contains(keyword))
        statement = (
            select(BlogPost)
            .where(*conditions)
            .order_by(BlogPost.updated_at.desc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_published(
        self,
        session: AsyncSession | None = None,
        keyword: str | None = None,
    ) -> int:
        """统计已发布文章总数"""
        conditions = [BlogPost.status == PostStatus.Published]
        if keyword:
            conditions.append(BlogPost.title.contains(keyword))
        statement = select(func.count()).select_from(BlogPost).where(*conditions)
        result = await session.exec(statement)
        return result.one()
