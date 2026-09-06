from fastapi import APIRouter, status, Depends, Query
from common.utils.fastapiEX.exceptions import NotFoundError
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
    # 编码重复等校验失败抛 ValueError, 由全局处理器映射为 400
    return await service.add(dict_type)


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
    return await service.get_scroll(params)


@router.get("/list", summary="分页查询字典类型列表", response_model=PaginationResponse)
async def list_dict_types(
    pagination: PaginationParams = Depends(),
    keyword: str | None = Query(None, max_length=100, description="类型名称/编码模糊搜索"),
    is_active: bool | None = Query(None, description="状态过滤(true=启用/false=禁用)"),
    service: DictTypeService = Depends(get_dict_type_service),
) -> PaginationResponse:
    """
    分页查询字典类型列表(支持多字段过滤)
    :param pagination: 分页参数 (通过查询参数传递)
    :param keyword: 类型名称/编码模糊搜索
    :param is_active: 状态过滤(true=启用/false=禁用)
    :param service: 字典类型服务依赖注入
    :return: 分页响应结果
    """
    return await service.list_paged(
        pagination, keyword=keyword, is_active=is_active
    )


@router.get("/code/{type_code}", summary="根据编码获取字典类型", response_model=DictType)
async def get_dict_type_by_code(
    type_code: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> DictType:
    """
    根据编码获取字典类型详情, 字典类型不存在时返回404
    :param type_code: 字典类型编码
    :param service: 字典类型服务依赖注入
    :return: 字典类型详情
    """
    result = await service.get_by_code(type_code)
    if not result:
        raise NotFoundError("字典类型不存在")
    return result


@router.get("/{dict_type_id}", summary="获取单个字典类型", response_model=DictType)
async def get_dict_type(
    dict_type_id: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> DictType:
    """
    获取单个字典类型详情, 字典类型不存在时返回404
    :param dict_type_id: 字典类型ID
    :param service: 字典类型服务依赖注入
    :return: 字典类型详情
    """
    result = await service.get(dict_type_id)
    if not result:
        raise NotFoundError("字典类型不存在")
    return result


@router.delete("/{dict_type_id}", summary="删除字典类型", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_type(
    dict_type_id: str,
    service: DictTypeService = Depends(get_dict_type_service),
) -> None:
    """
    按ID删除字典类型记录(仅删除类型本身, 不级联删除其下字典项)
    ID不存在时返回 400 错误(dao 层 not-found 抛 ValueError, 由全局处理器映射)
    :param dict_type_id: 字典类型ID
    :param service: 字典类型服务依赖注入
    """
    await service.delete(dict_type_id)


@router.put("/{dict_type_id}", summary="更新字典类型", status_code=status.HTTP_204_NO_CONTENT)
async def update_dict_type(
    dict_type_id: str,
    dict_type: DictTypeUpdate,
    service: DictTypeService = Depends(get_dict_type_service),
) -> None:
    """
    按ID部分更新字典类型, 仅请求体中显式传入的字段生效
    ID不存在时返回 400 错误(dao 层 not-found 抛 ValueError, 由全局处理器映射)
    :param dict_type_id: 字典类型ID
    :param dict_type: 字典类型数据
    :param service: 字典类型服务依赖注入
    """
    await service.update(dict_type_id, dict_type)


app.include_router(router, prefix="/dict_types", tags=["字典类型"])