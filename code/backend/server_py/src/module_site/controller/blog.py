from module_site.config.server import module_app
from module_site.dependencies.blog import get_blog_post_service
from module_site.service.blog import BlogPostService
from module_site.do.blog import BlogPost, BlogPostCreate, BlogPostUpdate
from module_authorization.dependencies.permission import require_permission
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse

from fastapi import APIRouter, HTTPException, status, Depends, Query

router = APIRouter()


@router.post(
    "",
    summary="发布博客文章(markdown 在线编辑 或 关联 URL)",
    status_code=status.HTTP_201_CREATED,
    response_model=str,
)
async def create_blog_post(
    post: BlogPostCreate,
    current_user_id: str = Depends(require_permission("site", "blog", "create")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> str:
    """
    发布新博客文章
    :param post: 文章数据(source_type=markdown 时 content 为正文, =url 时 url 为外链)
    :param current_user_id: 当前登录用户ID(作者)
    :return: 创建的文章ID
    """
    try:
        return await service.add(post, current_user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/view/list",
    summary="分页查询已发布文章(展示页)",
    response_model=PaginationResponse,
)
async def list_published_posts(
    pagination: PaginationParams = Depends(),
    keyword: str | None = Query(None, max_length=100, description="标题关键词"),
    _current_user_id: str = Depends(require_permission("site", "blog", "read")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> PaginationResponse:
    """
    分页查询已发布的博客文章(展示页内容, 需 site:blog:read 权限)
    :param keyword: 标题关键词过滤
    """
    try:
        return await service.list_published(pagination, keyword=keyword)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/list",
    summary="分页查询我的文章列表(管理页)",
    response_model=PaginationResponse,
)
async def list_my_posts(
    pagination: PaginationParams = Depends(),
    title: str | None = Query(None, max_length=100, description="标题模糊搜索"),
    status_filter: str | None = Query(None, alias="status", description="状态过滤(draft/published)"),
    source_filter: str | None = Query(None, alias="source_type", description="来源过滤(markdown/url)"),
    current_user_id: str = Depends(require_permission("site", "blog", "read")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> PaginationResponse:
    """
    分页查询当前用户的博客文章列表(管理页, 仅本人文章)
    """
    try:
        return await service.list_mine(
            pagination,
            current_user_id,
            title=title,
            status=status_filter,
            source_type=source_filter,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 低优先级路由(放在 /list /view/list 之后)
@router.get("/{post_id}", summary="获取单篇文章详情", response_model=BlogPost)
async def get_blog_post(
    post_id: str,
    current_user_id: str = Depends(require_permission("site", "blog", "read")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> BlogPost:
    """
    获取文章详情(草稿仅作者可见, 已发布文章对持有 read 权限的用户可见)
    """
    try:
        result = await service.get_visible(post_id, current_user_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="博客文章不存在"
            )
        return result
    except HTTPException:
        # 保留 404 语义,避免被通用异常处理包装成 500
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{post_id}", summary="删除博客文章", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_blog_post(
    post_id: str,
    current_user_id: str = Depends(require_permission("site", "blog", "delete")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> None:
    """删除本人博客文章(仅作者可删)"""
    try:
        await service.delete(post_id, current_user_id)
    except ValueError as e:
        # 资源不存在或不属于当前用户 → 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{post_id}", summary="更新博客文章", status_code=status.HTTP_204_NO_CONTENT
)
async def update_blog_post(
    post_id: str,
    post: BlogPostUpdate,
    current_user_id: str = Depends(require_permission("site", "blog", "update")),
    service: BlogPostService = Depends(get_blog_post_service),
) -> None:
    """更新本人博客文章(支持改标题/正文/外链/状态等)"""
    try:
        await service.update(post_id, post, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


module_app.include_router(router, prefix="/blog/posts", tags=["个人小站-博客"])
