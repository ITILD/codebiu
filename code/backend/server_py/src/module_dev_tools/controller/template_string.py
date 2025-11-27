"""
模板字符串控制器
提供基于string.Template的模板管理API
"""

from module_dev_tools.config.server import module_app
from module_dev_tools.dependencies.template_string import get_template_string_service
from module_dev_tools.service.template_string import TemplateStringService
from module_dev_tools.do.template_string import (
    TemplateString,
    TemplateStringCreate,
    TemplateStringUpdate,
    TemplateRenderRequest,
    TemplateRenderResponse,
)
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends

router = APIRouter()


@router.post(
    "", summary="创建模板字符串", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_template_string(
    template_string: TemplateStringCreate,
    service: TemplateStringService = Depends(get_template_string_service),
) -> str:
    """
    创建新模板字符串
    :param template_string: 模板字符串数据
    :param service: 模板字符串服务依赖注入
    :return: 创建的模板字符串ID
    """
    try:
        # 验证模板语法
        validation_result = await service.validate_template_syntax(template_string.template_content)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result["message"]
            )
        
        return await service.add(template_string)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/scroll", summary="滚动加载模板字符串")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: TemplateStringService = Depends(get_template_string_service),
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


@router.get("/list", summary="分页查询模板字符串列表", response_model=PaginationResponse)
async def list_template_strings(
    pagination: PaginationParams = Depends(),
    service: TemplateStringService = Depends(get_template_string_service),
) -> PaginationResponse:
    """
    分页查询模板字符串列表
    :param pagination: 分页参数
    :param service: 模板字符串服务依赖注入
    :return: 分页响应结果
    """
    try:
        pagination_response = await service.list_all(pagination)
        return pagination_response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{template_string_id}", summary="获取单个模板字符串", response_model=TemplateString)
async def get_template_string(
    template_string_id: str,
    service: TemplateStringService = Depends(get_template_string_service),
) -> TemplateString:
    """
    获取单个模板字符串详情
    :param template_string_id: 模板字符串ID
    :param service: 模板字符串服务依赖注入
    :return: 模板字符串详情
    """
    try:
        result = await service.get(template_string_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template string not found"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{template_string_id}", summary="删除模板字符串", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_template_string(
    template_string_id: str,
    service: TemplateStringService = Depends(get_template_string_service),
) -> None:
    """
    删除模板字符串
    :param template_string_id: 模板字符串ID
    :param service: 模板字符串服务依赖注入
    """
    try:
        await service.delete(template_string_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{template_string_id}", summary="更新模板字符串", status_code=status.HTTP_204_NO_CONTENT
)
async def update_template_string(
    template_string_id: str,
    template_string: TemplateStringUpdate,
    service: TemplateStringService = Depends(get_template_string_service),
) -> None:
    """
    更新模板字符串
    :param template_string_id: 模板字符串ID
    :param template_string: 模板字符串数据
    :param service: 模板字符串服务依赖注入
    """
    try:
        # 验证模板语法
        validation_result = await service.validate_template_syntax(template_string.template_content)
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result["message"]
            )
        
        await service.update(template_string_id, template_string)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/render", summary="渲染模板", response_model=TemplateRenderResponse)
async def render_template(
    render_request: TemplateRenderRequest,
    service: TemplateStringService = Depends(get_template_string_service),
) -> TemplateRenderResponse:
    """
    渲染模板
    :param render_request: 渲染请求
    :param service: 模板字符串服务依赖注入
    :return: 渲染结果
    """
    try:
        return await service.render_template(render_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )




@router.post("/validate", summary="验证模板语法")
async def validate_template_syntax(
    template_content: str,
    service: TemplateStringService = Depends(get_template_string_service),
) -> dict:
    """
    验证模板语法
    :param template_content: 模板内容
    :param service: 模板字符串服务依赖注入
    :return: 验证结果
    """
    try:
        return await service.validate_template_syntax(template_content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 将路由挂载到模块应用
module_app.include_router(router, prefix="/template_strings", tags=["模板字符串管理"])