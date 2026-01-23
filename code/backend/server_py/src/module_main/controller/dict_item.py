from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_main.do.dict_item import DictItem, DictItemCreate, DictItemUpdate
from module_main.dependencies.dict_item import get_dict_item_service
from module_main.service.dict_item import DictItemService
from common.config.server import app

router = APIRouter()


@router.post("", summary="创建字典项", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_dict_item(
    dict_item: DictItemCreate, service: DictItemService = Depends(get_dict_item_service)
) -> str:
    """
    创建新字典项
    :param dict_item: 字典项数据
    :param service: 字典项服务依赖注入
    :return: 创建的字典项ID
    """
    try:
        return await service.add(dict_item)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/scroll", summary="滚动加载字典项")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: DictItemService = Depends(get_dict_item_service),
) -> InfiniteScrollResponse:
    """
    无限滚动接口实现
    :param params: 分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    try:
        infinite_scroll_response = await service.get_scroll(params)
        return infinite_scroll_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页查询字典项列表", response_model=PaginationResponse)
async def list_dict_items(
    pagination: PaginationParams = Depends(),
    service: DictItemService = Depends(get_dict_item_service),
) -> PaginationResponse:
    """
    分页查询字典项列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 字典项服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list_all(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/dict_type/{type_code}", summary="根据字典类型编码查询字典项列表", response_model=list[DictItem])
async def list_dict_items_by_type(
    type_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> list[DictItem]:
    """
    根据字典类型编码查询字典项列表
    :param type_code: 字典类型编码
    :param service: 字典项服务依赖注入
    :return: 字典项列表
    """
    try:
        result = await service.list_by_dict_type(type_code)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/count/dict_type/{type_code}", summary="根据字典类型统计字典项数量", response_model=int)
async def count_dict_items_by_type(
    type_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> int:
    """
    根据字典类型统计字典项数量
    :param type_code: 字典类型编码
    :param service: 字典项服务依赖注入
    :return: 字典项数量
    """
    try:
        return await service.count_by_dict_type(type_code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/code/{item_code}", summary="根据编码获取字典项", response_model=DictItem)
async def get_dict_item_by_code(
    item_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> DictItem:
    """
    根据编码获取字典项详情
    :param item_code: 字典项编码
    :param service: 字典项服务依赖注入
    :return: 字典项详情
    """
    try:
        result = await service.get_by_code(item_code)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DictItem not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{dict_item_id}", summary="获取单个字典项", response_model=DictItem)
async def get_dict_item(
    dict_item_id: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> DictItem:
    """
    获取单个字典项详情
    :param dict_item_id: 字典项ID
    :param service: 字典项服务依赖注入
    :return: 字典项详情
    """
    try:
        result = await service.get(dict_item_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DictItem not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{dict_item_id}", summary="删除字典项", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_item(
    dict_item_id: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> None:
    """
    删除字典项
    :param dict_item_id: 字典项ID
    :param service: 字典项服务依赖注入
    """
    try:
        await service.delete(dict_item_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{dict_item_id}", summary="更新字典项", status_code=status.HTTP_204_NO_CONTENT)
async def update_dict_item(
    dict_item_id: str,
    dict_item: DictItemUpdate,
    service: DictItemService = Depends(get_dict_item_service),
) -> None:
    """
    更新字典项
    :param dict_item_id: 字典项ID
    :param dict_item: 字典项数据
    :param service: 字典项服务依赖注入
    """
    try:
        await service.update(dict_item_id, dict_item)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


app.include_router(router, prefix="/dict_items", tags=["字典项"])