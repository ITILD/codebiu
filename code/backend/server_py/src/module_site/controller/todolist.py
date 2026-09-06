from datetime import datetime

from module_site.config.server import module_app
from module_site.dependencies.todolist import get_todolist_service
from module_site.service.todolist import TodolistService
from module_site.do.todolist import Todolist, TodolistCreate, TodolistUpdate
from module_authorization.dependencies.permission import require_permission
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse

from fastapi import APIRouter, HTTPException, status, Depends, Query

router = APIRouter()


@router.post(
    "", summary="创建备忘", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_todolist(
    todolist: TodolistCreate,
    current_user_id: str = Depends(require_permission("site", "memo", "create")),
    service: TodolistService = Depends(get_todolist_service),
) -> str:
    """
    创建新备忘(归属当前用户, start_at 为日历展示时间)
    :param todolist: 备忘数据
    :return: 创建的备忘ID
    """
    try:
        return await service.add(todolist, current_user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/range", summary="按时间范围查询备忘(日历 年/月/周 视图数据源)"
)
async def list_memos_by_range(
    start: datetime = Query(..., description="范围起始(含), 带时区的 ISO 时间"),
    end: datetime = Query(..., description="范围结束(不含), 带时区的 ISO 时间"),
    current_user_id: str = Depends(require_permission("site", "memo", "read")),
    service: TodolistService = Depends(get_todolist_service),
) -> list[Todolist]:
    """
    查询 [start, end) 范围内的本人备忘列表
    - 年视图: 传整年起止; 月视图: 传整月起止; 周视图: 传本周起止
    - 前端按本地日历日分组展示
    """
    try:
        return await service.list_in_range(current_user_id, start, end)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页查询备忘列表(管理页)", response_model=PaginationResponse)
async def list_todolists(
    pagination: PaginationParams = Depends(),
    name: str | None = Query(None, max_length=100, description="备忘标题模糊搜索"),
    status_filter: str | None = Query(
        None, alias="status", description="状态过滤(todo=待办/done=完成/pause=暂停)"
    ),
    current_user_id: str = Depends(require_permission("site", "memo", "read")),
    service: TodolistService = Depends(get_todolist_service),
) -> PaginationResponse:
    """
    分页查询本人备忘列表(支持名称/状态过滤)
    """
    try:
        return await service.list_mine(
            pagination, current_user_id, name=name, status=status_filter
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 低优先级路由(放在 /range /list 之后)
@router.get("/{todolist_id}", summary="获取单个备忘", response_model=Todolist)
async def get_todolist(
    todolist_id: str,
    current_user_id: str = Depends(require_permission("site", "memo", "read")),
    service: TodolistService = Depends(get_todolist_service),
) -> Todolist:
    """获取备忘详情(仅本人可见)"""
    try:
        result = await service.get(todolist_id, current_user_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="备忘不存在"
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
    "/{todolist_id}", summary="删除备忘", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_todolist(
    todolist_id: str,
    current_user_id: str = Depends(require_permission("site", "memo", "delete")),
    service: TodolistService = Depends(get_todolist_service),
) -> None:
    """删除本人备忘"""
    try:
        await service.delete(todolist_id, current_user_id)
    except ValueError as e:
        # 资源不存在或不属于当前用户 → 404
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{todolist_id}", summary="更新备忘", status_code=status.HTTP_204_NO_CONTENT
)
async def update_todolist(
    todolist_id: str,
    todolist: TodolistUpdate,
    current_user_id: str = Depends(require_permission("site", "memo", "update")),
    service: TodolistService = Depends(get_todolist_service),
) -> None:
    """更新本人备忘(标题/内容/时间/状态等)"""
    try:
        await service.update(todolist_id, todolist, current_user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


module_app.include_router(router, prefix="/todolists", tags=["个人小站-备忘"])
