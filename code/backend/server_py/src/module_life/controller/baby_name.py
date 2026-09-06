from module_life.config.server import module_app
from module_life.dependencies.baby_name import get_baby_name_service
from module_life.service.baby_name import BabyNameService
from module_life.do.baby_name import (
    BabyName,
    BabyNameCreate,
    BabyNameUpdate,
    BabyNameBatchDelete,
)
from module_life.utils.baby_name.do.baby_name import (
    NameInfoBase,
    NameInfoFull,
    NameInfoResultList,
    NameInfoResult,
    NameInfoPreference,
    NameInfoResultExplanation,
    NameInfoResultBase,
    NameInfoEX,
    NameInfoPredictFull,
    NameInfoPredictFullRequest,
)
from common.utils.db.schema.pagination import (
    InfiniteScrollParams,
    InfiniteScrollResponse,
    PaginationParams,
    PaginationResponse,
)

from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.fastapiEX.exceptions import NotFoundError
from module_ai.utils.llm.response.sse import event_generator
from sse_starlette import EventSourceResponse


router = APIRouter()


# 根据name_info推测五行和星座等偏好信息
@router.post(
    "/predict-name-info-preference",
    summary="推测五行星座等偏好信息",
    status_code=status.HTTP_200_OK,
    response_model=NameInfoPreference,
)
async def predict_name_info_preference(
    name_info_base: NameInfoBase,
    service: BabyNameService = Depends(get_baby_name_service),
) -> NameInfoPreference:
    """
    根据宝宝天生信息推测适合的五行、星座等名字偏好，用于缩小取名范围
    :param name_info_base: 姓名信息基础数据(宝宝天生信息)
    :param service: 宝宝名字服务依赖注入
    :return: 推测的偏好信息(单个对象)
    """
    return await service.predict_name_info_preference_by_ai(name_info_base)


@router.post(
    "/predict",
    summary="推测宝宝名字",
    status_code=status.HTTP_200_OK,
    response_model=NameInfoResultList,
)
async def predict_baby_name(
    name_info_base: NameInfoBase,
    service: BabyNameService = Depends(get_baby_name_service),
) -> NameInfoResultList:
    """
    根据宝宝天生信息推测候选宝宝名字，返回名字结果列表
    :param name_info_base: 姓名信息基础数据
    :param service: 宝宝名字服务依赖注入
    :return: 推测结果列表
    """
    return await service.predict_name_by_ai(name_info_base)


@router.post(
    "/predict-baby-info-base",
    summary="推测宝宝五行星座名字的简易接口",
    status_code=status.HTTP_200_OK,
    response_model=NameInfoResultList,
)
async def predict_baby_info_base(
    request: NameInfoPredictFullRequest,
    service: BabyNameService = Depends(get_baby_name_service),
) :
    """
    根据宝宝完整基础信息推测名字，按请求中的 model_id 加载 LLM，以 SSE 事件流形式返回推测结果
    :param request: 宝宝信息与 model_id 等推测参数
    :param service: 宝宝名字服务依赖注入
    :return: SSE 事件流
    """
    # SSE 流式端点: 响应开始后无法再转 JSON, 端点体内的异常处理保留
    try:
        # 调用LLM服务
        responses = await service.predict_baby_info_base_by_ai(
            name_info_predict_full=request, model_id=request.model_id
        )
        # 流式响应SSE事件流
        return EventSourceResponse(
            event_generator(responses), media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 根据名字反推五行和星座等偏好信息和寓意
@router.post(
    "/predict-name-info-preference-meaning",
    summary="推测五行星座等偏好信息和寓意",
    status_code=status.HTTP_200_OK,
    response_model=NameInfoResultExplanation,
)
async def predict_name_info_preference_meaning(
    name_info_result_base: NameInfoResultBase,
    service: BabyNameService = Depends(get_baby_name_service),
) -> NameInfoResultExplanation:
    """
    根据宝宝姓氏与名字反推五行、星座等偏好，并给出名字的寓意解释
    :param name_info_result_base: 宝宝姓名基础信息(姓+名)
    :param service: 宝宝名字服务依赖注入
    :return: 偏好与寓意解释结果
    """
    return await service.predict_name_explanation_by_ai(name_info_result_base)


@router.post(
    "", summary="添加宝宝名字", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_baby_name(
    baby_name: BabyNameCreate, service: BabyNameService = Depends(get_baby_name_service)
) -> str:
    """
    生成新的宝宝名字
    :param baby_name: 宝宝名字生成参数
    :param service: 宝宝名字服务依赖注入
    :return: 生成的名字ID
    """
    return await service.add(baby_name)


@router.get("", summary="获取宝宝名字列表")
async def list_baby_names(
    params: PaginationParams = Depends(),
    service: BabyNameService = Depends(get_baby_name_service),
) -> PaginationResponse:
    """
    分页查询已保存的宝宝名字列表
    :param params: 分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    return await service.list_paged(params)


@router.get("/scroll", summary="滚动加载宝宝名字列表")
async def infinite_scroll(
    params: InfiniteScrollParams = Depends(),
    service: BabyNameService = Depends(get_baby_name_service),
) -> InfiniteScrollResponse:
    """
    无限滚动接口实现
    :param params: 滚动分页参数
    :param service: 服务层依赖
    :return: 分页响应数据
    """
    return await service.get_scroll(params)


@router.get("/{name_id}", summary="获取单个宝宝名字详情")
async def get_baby_name(
    name_id: str, service: BabyNameService = Depends(get_baby_name_service)
) -> BabyName:
    """
    按 ID 查询单个宝宝名字详情，名字不存在时返回 404
    :param name_id: 名字ID
    :param service: 服务层依赖
    :return: 宝宝名字详情
    """
    # 名字不存在时返回 404(由全局异常处理器统一响应)
    result = await service.get(name_id)
    if not result:
        raise NotFoundError("名字不存在")
    return result


@router.put("/{name_id}", summary="更新宝宝名字")
async def update_baby_name(
    name_id: str,
    baby_name: BabyNameUpdate,
    service: BabyNameService = Depends(get_baby_name_service),
):
    """
    更新宝宝名字信息
    :param name_id: 名字ID
    :param baby_name: 更新数据
    :param service: 服务层依赖
    """
    try:
        await service.update(name_id, baby_name)
    except ValueError as e:
        # 资源不存在 → 404(与 geometry 等模块错误映射保持一致)
        raise NotFoundError(str(e))


@router.delete("/{name_id}", summary="删除宝宝名字")
async def delete_baby_name(
    name_id: str, service: BabyNameService = Depends(get_baby_name_service)
):
    """
    按 ID 删除宝宝名字记录，名字不存在时返回 404
    :param name_id: 名字ID
    :param service: 服务层依赖
    """
    try:
        await service.delete(name_id)
    except ValueError as e:
        # 资源不存在 → 404
        raise NotFoundError(str(e))


@router.post("/batch-delete", summary="批量删除宝宝名字")
async def batch_delete_baby_names(
    batch_delete: BabyNameBatchDelete,
    service: BabyNameService = Depends(get_baby_name_service),
) -> int:
    """
    按 ID 列表批量删除宝宝名字记录，返回实际删除条数
    :param batch_delete: 批量删除请求
    :param service: 服务层依赖
    :return: 删除的记录数
    """
    return await service.batch_delete(batch_delete)


# 将路由注册到模块应用
module_app.include_router(router, prefix="/baby-names", tags=["宝宝名字管理"])
