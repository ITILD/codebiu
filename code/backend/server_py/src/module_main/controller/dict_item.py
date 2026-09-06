from fastapi import APIRouter, status, Depends
from common.utils.fastapiEX.exceptions import NotFoundError
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
    # 编码重复等校验失败抛 ValueError, 由全局处理器映射为 400
    return await service.add(dict_item)


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
    return await service.get_scroll(params)


@router.get("/list", summary="分页查询字典项列表", response_model=PaginationResponse)
async def list_dict_items(
    pagination: PaginationParams = Depends(),
    service: DictItemService = Depends(get_dict_item_service),
) -> PaginationResponse:
    """
    按分页参数返回字典项数据页, 不做任何条件过滤
    total 为字典项全表总数
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 字典项服务依赖注入
    :return: 分页响应结果
    """
    return await service.list_paged(pagination)


@router.get("/by-type/{type_code}", summary="根据字典类型编码查询字典项列表", response_model=list[DictItem])
async def list_dict_items_by_type(
    type_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> list[DictItem]:
    """
    先按 type_code 定位字典类型, 再返回其下全部字典项(按 sort_order 排序)
    类型编码不存在时返回空列表
    :param type_code: 字典类型编码
    :param service: 字典项服务依赖注入
    :return: 字典项列表
    """
    return await service.list_by_dict_type(type_code)


@router.get("/by-type/{type_code}/count", summary="根据字典类型统计字典项数量", response_model=int)
async def count_dict_items_by_type(
    type_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> int:
    """
    先按 type_code 定位字典类型, 再统计该类型下字典项数量
    类型编码不存在时返回 0
    :param type_code: 字典类型编码
    :param service: 字典项服务依赖注入
    :return: 字典项数量
    """
    return await service.count_by_dict_type(type_code)


@router.get("/code/{item_code}", summary="根据编码获取字典项", response_model=DictItem)
async def get_dict_item_by_code(
    item_code: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> DictItem:
    """
    根据编码获取字典项详情, 字典项不存在时返回404
    :param item_code: 字典项编码
    :param service: 字典项服务依赖注入
    :return: 字典项详情
    """
    result = await service.get_by_code(item_code)
    if not result:
        raise NotFoundError("字典项不存在")
    return result


@router.get("/{dict_item_id}", summary="获取单个字典项", response_model=DictItem)
async def get_dict_item(
    dict_item_id: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> DictItem:
    """
    获取单个字典项详情, 字典项不存在时返回404
    :param dict_item_id: 字典项ID
    :param service: 字典项服务依赖注入
    :return: 字典项详情
    """
    result = await service.get(dict_item_id)
    if not result:
        raise NotFoundError("字典项不存在")
    return result


@router.delete("/{dict_item_id}", summary="删除字典项", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dict_item(
    dict_item_id: str,
    service: DictItemService = Depends(get_dict_item_service),
) -> None:
    """
    按ID删除字典项记录
    ID不存在时返回 400 错误(dao 层 not-found 抛 ValueError, 由全局处理器映射)
    :param dict_item_id: 字典项ID
    :param service: 字典项服务依赖注入
    """
    await service.delete(dict_item_id)


@router.put("/{dict_item_id}", summary="更新字典项", status_code=status.HTTP_204_NO_CONTENT)
async def update_dict_item(
    dict_item_id: str,
    dict_item: DictItemUpdate,
    service: DictItemService = Depends(get_dict_item_service),
) -> None:
    """
    按ID部分更新字典项, 仅请求体中显式传入的字段生效
    ID不存在时返回 400 错误(dao 层 not-found 抛 ValueError, 由全局处理器映射)
    :param dict_item_id: 字典项ID
    :param dict_item: 字典项数据
    :param service: 字典项服务依赖注入
    """
    await service.update(dict_item_id, dict_item)


app.include_router(router, prefix="/dict_items", tags=["字典项"])