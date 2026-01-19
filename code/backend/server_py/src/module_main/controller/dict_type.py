from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)
from module_main.do.dict_type import DictType, DictTypeCreate, DictTypeUpdate
from module_main.dependencies.dict_type import get_dict_type_service
from module_main.service.dict_type import DictTypeService
from common.config.server import app

router = APIRouter()


@router.post("", summary="创建字典类型", status_code=status.HTTP_201_CREATED, response_model=str)
async def create_dict_type(
    dict_type: DictTypeCreate, service: DictTypeService = Depends(get_dict_type_service)
) -> str:
    """
    创建新字典类型
    :param dict_type: 字典类型数据
    :param service: 字典类型服务依赖注入
    :return: 创建的字典类型ID
    """
    try:
        return await service.add(dict_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/scroll", summary="滚动加载字典类型")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: DictTypeService = Depends(get_dict_type_service),
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


@router.get("/list", summary="分页查询字典类型列表", response_model=PaginationResponse)
async def list_dict_types(
    pagination: PaginationParams = Depends(),
    service: DictTypeService = Depends(get_dict_type_service),
) -> PaginationResponse:
    """
    分页查询字典类型列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 字典类型服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list_all(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/code/{type_code}", summary="根据编码获取字典类型", response_model=DictType)
async def get_dict_type_by_code(
    type_code: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> DictType:
    """
    根据编码获取字典类型详情
    :param type_code: 字典类型编码
    :param service: 字典类型服务依赖注入
    :return: 字典类型详情
    """
    try:
        result = await service.get_by_code(type_code)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DictType not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{dict_type_id}", summary="获取单个字典类型", response_model=DictType)
async def get_dict_type(
    dict_type_id: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> DictType:
    """
    获取单个字典类型详情
    :param dict_type_id: 字典类型ID
    :param service: 字典类型服务依赖注入
    :return: 字典类型详情
    """
    try:
        result = await service.get(dict_type_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="DictType not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{dict_type_id}", summary="删除字典类型", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_type(
    dict_type_id: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> None:
    """
    删除字典类型
    :param dict_type_id: 字典类型ID
    :param service: 字典类型服务依赖注入
    """
    try:
        await service.delete(dict_type_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{dict_type_id}", summary="更新字典类型", status_code=status.HTTP_204_NO_CONTENT)
async def update_dict_type(
    dict_type_id: str,
    dict_type: DictTypeUpdate,
    service: DictTypeService = Depends(get_dict_type_service),
) -> None:
    """
    更新字典类型
    :param dict_type_id: 字典类型ID
    :param dict_type: 字典类型数据
    :param service: 字典类型服务依赖注入
    """
    try:
        await service.update(dict_type_id, dict_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


app.include_router(router, prefix="/dict_types", tags=["字典类型"])