from module_template.config.server import module_app
from module_template.dependencies.template import get_template_service
from module_template.service.template import TemplateService
from module_template.do.template import Template, TemplateCreate, TemplateUpdate, TemplateBatchDelete
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, status, Depends
from common.utils.fastapiEX.exceptions import NotFoundError

router = APIRouter()

@router.post(
    "", summary="创建模板", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_template(
    template: TemplateCreate, service: TemplateService = Depends(get_template_service)
) -> str:
    """
    创建新模板
    :param template: 模板数据
    :param service: 模板服务依赖注入
    :return: 创建的模板ID
    """
    return await service.add(template)


@router.get("/scroll", summary="滚动加载 考虑路由顺序")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: TemplateService = Depends(get_template_service),
)-> InfiniteScrollResponse:
    """
    无限滚动接口实现
    :param params: 分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    infinite_scroll_response = await service.get_scroll(params)
    return infinite_scroll_response


@router.get("/list", summary="分页查询模板列表", response_model=PaginationResponse)
async def list_templates(
    pagination: PaginationParams = Depends(),
    service: TemplateService = Depends(get_template_service),
) -> PaginationResponse:
    """
    按分页参数返回模板数据页, 不做任何条件过滤
    total 为模板全表总数
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 模板服务依赖注入
    :return: 分页响应结果
    """
    pagination_response: PaginationResponse = await service.list_paged(pagination)
    return pagination_response


# 低优先级路由
@router.get("/{template_id}", summary="获取单个模板", response_model=Template)
async def get_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> Template:
    """
    获取单个模板详情
    :param template_id: 模板ID
    :param service: 模板服务依赖注入
    :return: 模板详情
    """
    # 模板不存在时返回 404(由全局异常处理器统一响应)
    result = await service.get(template_id)
    if not result:
        raise NotFoundError("模板不存在")
    return result


@router.delete(
    "/{template_id}", summary="删除模板", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> None:
    """
    按ID删除模板记录
    ID不存在时返回 404(detail 为 "未找到ID为 xxx 的模板")
    :param template_id: 模板ID
    :param service: 模板服务依赖注入
    """
    await service.delete(template_id)


@router.delete(
    "/batch", summary="批量删除模板", status_code=status.HTTP_200_OK
)
async def batch_delete_template(
    batch_delete: TemplateBatchDelete,
    service: TemplateService = Depends(get_template_service),
) -> dict:
    """
    按ID列表批量删除模板
    不存在的ID静默跳过, 返回实际删除数量 {deleted_count}
    :param batch_delete: 批量删除请求(包含ids列表)
    :param service: 模板服务依赖注入
    :return: 删除结果(包含实际删除数量)
    """
    deleted_count = await service.batch_delete(batch_delete)
    return {"deleted_count": deleted_count}


@router.put(
    "/{template_id}", summary="更新模板", status_code=status.HTTP_204_NO_CONTENT
)
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    service: TemplateService = Depends(get_template_service),
) -> None:
    """
    按ID部分更新模板, 仅请求体中显式传入的字段生效
    ID不存在时返回 404(detail 为 "未找到ID为 xxx 的模板")
    :param template_id: 模板ID
    :param template: 模板数据
    :param service: 模板服务依赖注入
    """
    # 确保更新的是指定ID的模板
    await service.update(template_id, template)


module_app.include_router(router, prefix="/templates", tags=["基础模板"])
