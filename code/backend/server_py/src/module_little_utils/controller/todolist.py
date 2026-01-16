from module_little_utils.config.server import module_app
from module_little_utils.dependencies.todolist import get_todolist_service
from module_little_utils.service.todolist import TodolistService
from module_little_utils.do.todolist import Todolist, TodolistCreate, TodolistUpdate
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends

router = APIRouter()

@router.post(
    "", summary="创建计划列表", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_todolist(
    todolist: TodolistCreate, service: TodolistService = Depends(get_todolist_service)
) -> str:
    """
    创建新计划列表
    :param todolist: 计划列表数据
    :param service: 计划列表服务依赖注入
    :return: 创建的计划列表ID
    """
    try:
        return await service.add(todolist)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/scroll", summary="滚动加载 考虑路由顺序")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: TodolistService = Depends(get_todolist_service),
)-> InfiniteScrollResponse:
    """
    无限滚动接口实现
    :param params: 分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    try:
        itnfinite_scroll_response = await service.get_scroll(params)
        return itnfinite_scroll_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页查询计划列表列表", response_model=PaginationResponse)
async def list_todolists(
    pagination: PaginationParams = Depends(),
    service: TodolistService = Depends(get_todolist_service),
) -> PaginationResponse:
    """
    分页查询计划列表列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 计划列表服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list_all(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 低优先级路由
@router.get("/{todolist_id}", summary="获取单个计划列表", response_model=Todolist)
async def get_todolist(
    todolist_id: str,
    service: TodolistService = Depends(get_todolist_service),
) -> Todolist:
    """
    获取单个计划列表详情
    :param todolist_id: 计划列表ID
    :param service: 计划列表服务依赖注入
    :return: 计划列表详情
    """
    try:
        result = await service.get(todolist_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Todolist not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{todolist_id}", summary="删除计划列表", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_todolist(
    todolist_id: str,
    service: TodolistService = Depends(get_todolist_service),
) -> None:
    """
    删除计划列表
    :param todolist_id: 计划列表ID
    :param service: 计划列表服务依赖注入
    """
    try:
        await service.delete(todolist_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{todolist_id}", summary="更新计划列表", status_code=status.HTTP_204_NO_CONTENT
)
async def update_todolist(
    todolist_id: str,
    todolist: TodolistUpdate,
    service: TodolistService = Depends(get_todolist_service),
) -> None:
    """
    更新计划列表
    :param todolist_id: 计划列表ID
    :param todolist: 计划列表数据
    :param service: 计划列表服务依赖注入
    """
    try:
        # 确保更新的是指定ID的计划列表
        await service.update(todolist_id, todolist)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


module_app.include_router(router, prefix="/todolist", tags=["基础计划列表"])
