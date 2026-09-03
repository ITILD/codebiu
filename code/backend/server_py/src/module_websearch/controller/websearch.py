from module_websearch.config.server import module_app
from module_websearch.dependencies.websearch import get_websearch_service
from module_websearch.service.websearch import WebSearchService
from module_websearch.utils.websearch.do.websearch import EngineInfo, SearchRequest, SearchResponse
from module_authorization.dependencies.permission import require_permission

from fastapi import APIRouter, HTTPException, status, Depends

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
    查询全部可用搜索引擎元信息(默认引擎排前,含是否需要/已配置 API Key)
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


@router.post(
    "/search",
    summary="网页搜索(默认 DuckDuckGo)",
    response_model=SearchResponse,
)
async def search(
    request: SearchRequest,
    current_user_id: str = Depends(require_permission("main", "search", "read")),
    service: WebSearchService = Depends(get_websearch_service),
) -> SearchResponse:
    """
    执行网页搜索
    :param request: 搜索请求体(查询信息/引擎/条数上限/时间范围/屏蔽站点)
    :param current_user_id: 当前登录用户ID(权限依赖注入)
    :param service: 搜索服务依赖注入
    :return: 搜索响应(标题/链接/摘要/来源/发布时间)
    """
    try:
        return await service.search(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # 网络类异常(如超时)的 str 可能为空,补充异常类型名便于排查
        detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"搜索引擎请求失败: {detail}",
        )


# 挂载后完整路径: /websearch/engines 与 /websearch/search
module_app.include_router(router, prefix="", tags=["网页搜索"])
