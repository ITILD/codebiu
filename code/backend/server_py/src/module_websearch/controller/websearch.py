from module_websearch.config.server import module_app
from module_websearch.dependencies.websearch import get_websearch_service
from module_websearch.service.websearch import WebSearchService
from module_websearch.do.websearch import EngineInfo, SearchResponse
from module_authorization.dependencies.permission import require_permission

from fastapi import APIRouter, HTTPException, Query, status, Depends

router = APIRouter()


@router.get(
    "/engines",
    summary="查询可用搜索引擎列表",
    response_model=list[EngineInfo],
)
async def list_engines(
    current_user_id: str = Depends(require_permission("main", "search", "read")),
    service: WebSearchService = Depends(get_websearch_service),
) -> list[EngineInfo]:
    """
    查询全部可用搜索引擎元信息(默认引擎排前)
    :param current_user_id: 当前登录用户ID(权限依赖注入)
    :param service: 搜索服务依赖注入
    :return: 引擎元信息列表
    """
    try:
        return service.list_engines()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/search",
    summary="网页搜索(默认 DuckDuckGo)",
    response_model=SearchResponse,
)
async def search(
    query: str = Query(..., min_length=1, max_length=200, description="查询词"),
    engine: str | None = Query(
        None, max_length=32, description="引擎标识(duckduckgo/bing,为空用默认)"
    ),
    limit: int | None = Query(
        None, ge=1, le=30, description="返回条数上限(为空用配置,上限30)"
    ),
    current_user_id: str = Depends(require_permission("main", "search", "read")),
    service: WebSearchService = Depends(get_websearch_service),
) -> SearchResponse:
    """
    执行网页搜索
    :param query: 查询词
    :param engine: 引擎标识(为空使用默认引擎 duckduckgo)
    :param limit: 返回条数上限
    :param current_user_id: 当前登录用户ID(权限依赖注入)
    :param service: 搜索服务依赖注入
    :return: 搜索响应(标题/链接/摘要/来源)
    """
    try:
        return await service.search(query, engine, limit)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"搜索引擎请求失败: {e}",
        )


# 挂载后完整路径: /websearch/engines 与 /websearch/search
module_app.include_router(router, prefix="", tags=["网页搜索"])
