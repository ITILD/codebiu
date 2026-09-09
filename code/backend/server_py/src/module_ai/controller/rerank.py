"""重排序(Rerank)控制器

接口：
- POST /rerank    文本重排序(query + documents -> 按相关性降序)

引擎方案由 model_config 表(model_type=rerank)驱动, 请求可指定 model_id 覆盖。
"""
import logging

from fastapi import APIRouter, Depends

from module_ai.config.server import module_app
from module_ai.dependencies.rerank import get_rerank_service
from module_ai.do.rerank import RerankRequest, RerankResponse
from module_ai.service.rerank import RerankService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=RerankResponse, summary="文本重排序")
async def rerank_documents(
    request: RerankRequest,
    rerank_service: RerankService = Depends(get_rerank_service),
) -> RerankResponse:
    """对文档列表按查询相关性重排序

    - **query**: 检索查询文本
    - **documents**: 待排序文档(字符串或含 sort_key 字段的字典)
    - **model_id**: 模型配置(缺省取 rerank 类型默认配置)
    """
    return await rerank_service.rerank(request)


# 将路由注册到模块应用
module_app.include_router(router, prefix="/rerank", tags=["重排序"])
