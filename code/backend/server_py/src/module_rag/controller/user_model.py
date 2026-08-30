from fastapi import APIRouter, HTTPException, status, Depends
from module_rag.do.user_model import UserModelUpdate, UserModelResponse
from module_rag.service.user_model import UserModelService
from module_rag.dependencies.user_model import get_user_model_service
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.config.server import module_app

router = APIRouter()


@router.get(
    "/my", summary="获取当前用户的模型绑定", response_model=UserModelResponse
)
async def get_my_model_binding(
    current_user_id: str = Depends(get_current_user_id),
    service: UserModelService = Depends(get_user_model_service),
):
    """
    获取当前登录用户的模型绑定(chat模型/向量化模型)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 用户-模型绑定服务依赖注入
    :return: 用户-模型绑定详情
    """
    try:
        result = await service.get_by_user(current_user_id)
        if not result:
            # 未绑定则返回空绑定
            return UserModelResponse(
                id="",
                user_id=current_user_id,
                chat_model_id=None,
                embedding_model_id=None,
                created_at=None,
                updated_at=None,
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/my", summary="更新当前用户的模型绑定", response_model=UserModelResponse
)
async def update_my_model_binding(
    user_model: UserModelUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: UserModelService = Depends(get_user_model_service),
):
    """
    更新当前登录用户的模型绑定(chat模型/向量化模型)
    :param user_model: 更新数据(chat_model_id/embedding_model_id)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 用户-模型绑定服务依赖注入
    :return: 更新后的用户-模型绑定详情
    """
    try:
        return await service.upsert(current_user_id, user_model)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/user-models", tags=["用户模型绑定"])
