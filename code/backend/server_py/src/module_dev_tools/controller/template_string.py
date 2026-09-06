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

from fastapi import APIRouter, status, Depends
from common.utils.fastapiEX.exceptions import BusinessError, NotFoundError

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
    # 验证模板语法(无效时拒绝创建, 返回 400)
    validation_result = await service.validate_template_syntax(template_string.template_content)
    if not validation_result["valid"]:
        raise BusinessError(validation_result["message"])

    return await service.add(template_string)


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
    infinite_scroll_response = await service.get_scroll(params)
    return infinite_scroll_response


@router.get("/list", summary="分页查询模板字符串列表", response_model=PaginationResponse)
async def list_template_strings(
    pagination: PaginationParams = Depends(),
    service: TemplateStringService = Depends(get_template_string_service),
) -> PaginationResponse:
    """
    按分页参数返回模板字符串数据页, 不做任何条件过滤
    total 为模板字符串全表总数
    :param pagination: 分页参数
    :param service: 模板字符串服务依赖注入
    :return: 分页响应结果
    """
    pagination_response = await service.list_paged(pagination)
    return pagination_response


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
    # 记录不存在时返回 404(由全局异常处理器统一响应)
    result = await service.get(template_string_id)
    if not result:
        raise NotFoundError("模板字符串不存在")
    return result


@router.delete(
    "/{template_string_id}", summary="删除模板字符串", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_template_string(
    template_string_id: str,
    service: TemplateStringService = Depends(get_template_string_service),
) -> None:
    """
    按ID删除模板字符串记录
    ID不存在时返回 404(detail 为 "未找到ID为 xxx 的模板字符串")
    :param template_string_id: 模板字符串ID
    :param service: 模板字符串服务依赖注入
    """
    await service.delete(template_string_id)


@router.put(
    "/{template_string_id}", summary="更新模板字符串", status_code=status.HTTP_204_NO_CONTENT
)
async def update_template_string(
    template_string_id: str,
    template_string: TemplateStringUpdate,
    service: TemplateStringService = Depends(get_template_string_service),
) -> None:
    """
    更新前先校验模板语法, 语法无效时拒绝更新
    按ID部分更新(仅显式传入字段生效); ID不存在时返回 404
    :param template_string_id: 模板字符串ID
    :param template_string: 模板字符串数据
    :param service: 模板字符串服务依赖注入
    """
    # 验证模板语法(无效时拒绝更新, 返回 400)
    validation_result = await service.validate_template_syntax(template_string.template_content)
    if not validation_result["valid"]:
        raise BusinessError(validation_result["message"])

    await service.update(template_string_id, template_string)


@router.post("/render", summary="渲染模板", response_model=TemplateRenderResponse)
async def render_template(
    render_request: TemplateRenderRequest,
    service: TemplateStringService = Depends(get_template_string_service),
) -> TemplateRenderResponse:
    """
    基于 string.Template 渲染模板: 优先使用请求体中的 template_content,
    未提供内容时按 template_id 从库中读取(两者均缺省时返回 400, 模板不存在时返回 404)
    缺失变量按原样保留并记入 variables_missing
    :param render_request: 渲染请求
    :param service: 模板字符串服务依赖注入
    :return: 渲染结果
    """
    return await service.render_template(render_request)



@router.post("/validate", summary="验证模板语法")
async def validate_template_syntax(
    template_content: str,
    service: TemplateStringService = Depends(get_template_string_service),
) -> dict:
    """
    校验模板内容是否符合 string.Template 语法, 并提取其中的 ${var} 变量列表
    语法错误不抛异常, 以 valid=false 返回
    :param template_content: 模板内容
    :param service: 模板字符串服务依赖注入
    :return: 验证结果
    """
    return await service.validate_template_syntax(template_content)
# TODO 凑文件夹压缩包规则,下载模板文件 只修改do

# 将路由挂载到模块应用
module_app.include_router(router, prefix="/template-strings", tags=["模板字符串管理"])
