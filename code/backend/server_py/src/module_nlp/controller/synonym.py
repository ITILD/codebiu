from module_nlp.config.server import module_app
from module_nlp.dependencies.synonym import get_synonym_group_service, get_synonym_service
from module_nlp.service.synonym import SynonymGroupService, SynonymService
from module_nlp.do.synonym import (
    SynonymGroup,
    SynonymGroupCreate,
    SynonymGroupUpdate,
    SynonymGroupBatchDelete,
    Synonym,
    SynonymBatchCreate,
    SynonymBatchDelete,
    SynonymBatchSearch,
    SynonymBatchSearchResult,
    SynonymBatchUpdate,
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
    "/groups", summary="创建同义词组", status_code=status.HTTP_201_CREATED, response_model=str
)
async def create_synonym_group(
    synonym_group: SynonymGroupCreate,
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> str:
    """
    创建新同义词组
    :param synonym_group: 同义词组数据
    :param service: 同义词组服务依赖注入
    :return: 创建的同义词组ID
    """
    try:
        return await service.add(synonym_group)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/groups/batch",
    summary="批量创建同义词",
    status_code=status.HTTP_201_CREATED,
    response_model=list[str],
)
async def batch_create_synonyms(
    batch_create: SynonymBatchCreate, service: SynonymService = Depends(get_synonym_service)
) -> list[str]:
    """
    批量创建同义词
    :param batch_create: 批量创建同义词请求
    :param service: 同义词服务依赖注入
    :return: 创建的同义词ID列表
    """
    try:
        return await service.batch_add(batch_create)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put(
    "/synonyms/batch/{group_id}", 
    summary="批量更新同义词", 
    status_code=status.HTTP_200_OK
)
async def batch_update_synonyms(
    group_id: str,
    batch_update: SynonymBatchUpdate,
    service: SynonymService = Depends(get_synonym_service)
) -> None:
    """
    批量更新同义词
    :param group_id: 同义词组ID
    :param batch_update: 批量更新同义词请求
    :param service: 同义词服务依赖注入
    :return: None
    """
    try:
        await service.batch_update(group_id, batch_update)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=str(e)
        )

@router.get("/groups/scroll", summary="同义词组滚动加载", response_model=InfiniteScrollResponse)
async def synonym_group_infinite_scroll(
    pid: str,
    params: InfiniteScrollParams = Depends(),
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> InfiniteScrollResponse:
    """
    同义词组无限滚动分页查询
    :param params: 分页参数
    :param pid: 项目ID
    :param service: 同义词组服务依赖注入
    :return: 分页响应数据
    """
    try:
        return await service.get_scroll_by_pid(params, pid)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/groups/list", summary="分页查询同义词组列表", response_model=PaginationResponse)
async def list_synonym_groups(
    pid: str,
    pagination: PaginationParams = Depends(),
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> PaginationResponse:
    """
    分页查询同义词组列表
    :param pagination: 分页参数
    :param pid: 项目ID
    :param service: 同义词组服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_all_by_pid(pagination, pid)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/groups/{group_id}", summary="获取单个同义词组", response_model=SynonymGroup)
async def get_synonym_group(
    group_id: str,
    pid: str,
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> SynonymGroup:
    """
    获取单个同义词组详情
    :param group_id: 同义词组ID
    :param pid: 项目ID
    :param service: 同义词组服务依赖注入
    :return: 同义词组详情
    """
    try:
        result = await service.get_by_id_and_pid(group_id, pid)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="同义词组未找到")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/groups/{group_id}/synonyms", summary="获取同义词组的所有同义词", response_model=list[str]
)
async def get_synonyms_by_group(
    group_id: str,
    service: SynonymService = Depends(get_synonym_service),
) -> list[str]:
    """
    获取同义词组的所有同义词(仅返回词语列表)
    :param group_id: 同义词组ID
    :param service: 同义词服务依赖注入
    :return: 同义词词语列表
    """
    try:
        return await service.get_synonyms_by_group(group_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/synonyms/search", summary="同义词查找", response_model=list[Synonym])
async def search_synonyms(
    word: str,
    pid: str,
    language: str | None = None,
    service: SynonymService = Depends(get_synonym_service),
) -> list[Synonym]:
    """
    根据词语搜索其所在同义词组的所有同义词
    :param word: 要搜索的词语
    :param pid: 项目ID
    :param language: 语言代码(可选)
    :param service: 同义词服务依赖注入
    :return: 该词语所在同义词组的所有同义词列表
    """
    try:
        return await service.search_by_word(word, pid, language)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/groups/{group_id}", summary="删除同义词组", status_code=status.HTTP_204_NO_CONTENT)
async def delete_synonym_group(
    group_id: str,
    pid: str,
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> None:
    """
    删除同义词组
    :param group_id: 同义词组ID
    :param pid: 项目ID
    :param service: 同义词组服务依赖注入
    """
    try:
        await service.delete_by_id_and_pid(group_id, pid)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/groups/batch", summary="批量删除同义词组", status_code=status.HTTP_200_OK)
async def batch_delete_synonym_groups(
    pid: str,
    batch_delete: SynonymGroupBatchDelete,
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> dict:
    """
    批量删除同义词组
    :param batch_delete: 批量删除请求(包含ids列表)
    :param pid: 项目ID
    :param service: 同义词组服务依赖注入
    :return: 删除结果(包含实际删除数量)
    """
    try:
        deleted_count = await service.batch_delete_by_ids_and_pid(batch_delete, pid)
        return {"deleted_count": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete(
    "/synonyms/{synonym_id}", summary="删除同义词", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_synonym(
    synonym_id: str,
    pid: str,
    service: SynonymService = Depends(get_synonym_service),
) -> None:
    """
    删除同义词
    :param synonym_id: 同义词ID
    :param pid: 项目ID
    :param service: 同义词服务依赖注入
    """
    try:
        await service.delete_by_id_and_pid(synonym_id, pid)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/synonyms/batch", summary="批量删除同义词", status_code=status.HTTP_200_OK)
async def batch_delete_synonyms(
    batch_delete: SynonymBatchDelete,
    pid: str,
    service: SynonymService = Depends(get_synonym_service),
) -> dict:
    """
    批量删除同义词
    :param batch_delete: 批量删除请求(包含ids列表)
    :param pid: 项目ID
    :param service: 同义词服务依赖注入
    :return: 删除结果(包含实际删除数量)
    """
    try:
        deleted_count = await service.batch_delete_by_ids_and_pid(batch_delete, pid)
        return {"deleted_count": deleted_count}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/groups", summary="更新同义词组", status_code=status.HTTP_204_NO_CONTENT)
async def update_synonym_group(
    group_id: str,
    synonym_group: SynonymGroupUpdate,
    service: SynonymGroupService = Depends(get_synonym_group_service),
) -> None:
    """
    更新同义词组
    :param group_id: 同义词组ID
    :param synonym_group: 同义词组数据
    :param service: 同义词组服务依赖注入
    """
    try:
        await service.update(group_id, synonym_group)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/synonyms/search/batch",
    # TODO response_model=list[SynonymBatchSearchResult],
    summary="同义词批量查找",
)
async def batch_search_synonyms(
    request: SynonymBatchSearch,
    pid: str,
    service: SynonymService = Depends(get_synonym_service),
):
    """
    批量根据词语搜索其所在同义词组的所有同义词

    :param request: 批量搜索请求，包含词语列表和可选语言参数
    :param pid: 项目ID
    :param service: 同义词服务
    :return: 所有词语所在同义词组的所有同义词列表
    """
    try:
        results = await service.batch_search_by_words(
            words=request.words, pid=pid, language=request.language
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


module_app.include_router(router, prefix="/nlp/synonyms", tags=["同义词管理"])
