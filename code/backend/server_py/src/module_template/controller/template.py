from module_template.config.server import module_app
from module_template.dependencies.template import get_template_service
from module_template.service.template import TemplateService
from module_template.do.template import Template, TemplateCreate, TemplateUpdate
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends

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
    try:
        return await service.add(template)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


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
    try:
        itnfinite_scroll_response = await service.get_scroll(params)
        return itnfinite_scroll_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/list", summary="分页查询模板列表", response_model=PaginationResponse)
async def list_templates(
    pagination: PaginationParams = Depends(),
    service: TemplateService = Depends(get_template_service),
) -> PaginationResponse:
    """
    分页查询模板列表
    :param pagination: 分页参数 (通过查询参数传递)
    :param service: 模板服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response: PaginationResponse = await service.list(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


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
    try:
        result = await service.get(template_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{template_id}", summary="删除模板", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> None:
    """
    删除模板
    :param template_id: 模板ID
    :param service: 模板服务依赖注入
    """
    try:
        await service.delete(template_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{template_id}", summary="更新模板", status_code=status.HTTP_204_NO_CONTENT
)
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    service: TemplateService = Depends(get_template_service),
) -> None:
    """
    更新模板
    :param template_id: 模板ID
    :param template: 模板数据
    :param service: 模板服务依赖注入
    """
    try:
        # 确保更新的是指定ID的模板
        await service.update(template_id, template)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


module_app.include_router(router, prefix="/templates", tags=["基础模板"])
