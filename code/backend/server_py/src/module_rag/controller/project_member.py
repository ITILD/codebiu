from fastapi import APIRouter, HTTPException, status, Depends
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_member import (
    ProjectMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    MyProjectResponse,
)
from module_rag.service.project_member import ProjectMemberService
from module_rag.dependencies.project_member import get_project_member_service
from module_rag.config.server import module_app

router = APIRouter()


@router.post(
    "", summary="添加项目成员", status_code=status.HTTP_201_CREATED, response_model=str
)
async def add_project_member(
    member: ProjectMemberCreate,
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    添加项目成员
    :param member: 项目成员数据
    :param service: 项目成员服务依赖注入
    :return: 创建的项目成员ID
    """
    try:
        return await service.add(member)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/my/{user_id}", summary="获取我参与的项目", response_model=PaginationResponse
)
async def list_my_projects(
    user_id: str,
    pagination: PaginationParams = Depends(),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    获取我参与的项目列表（前端展示"我参与的项目及我的身份"）
    :param user_id: 用户ID
    :param pagination: 分页参数
    :param service: 项目成员服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_my_projects(user_id, pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/project/{project_id}", summary="获取项目成员列表", response_model=PaginationResponse
)
async def list_project_members(
    project_id: str,
    pagination: PaginationParams = Depends(),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    获取项目成员列表
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param service: 项目成员服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_by_project(project_id, pagination)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{member_id}", summary="获取单个项目成员", response_model=ProjectMember)
async def get_project_member(
    member_id: str,
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    获取单个项目成员详情
    :param member_id: 项目成员ID
    :param service: 项目成员服务依赖注入
    :return: 项目成员详情
    """
    try:
        result = await service.get(member_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="项目成员未找到"
            )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{member_id}", summary="移除项目成员", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_project_member(
    member_id: str,
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    移除项目成员
    :param member_id: 项目成员ID
    :param service: 项目成员服务依赖注入
    """
    try:
        await service.delete(member_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{member_id}", summary="更新项目成员角色", status_code=status.HTTP_204_NO_CONTENT
)
async def update_project_member(
    member_id: str,
    member: ProjectMemberUpdate,
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    更新项目成员角色
    :param member_id: 项目成员ID
    :param member: 项目成员更新数据
    :param service: 项目成员服务依赖注入
    """
    try:
        await service.update(member_id, member)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/project-members", tags=["项目成员管理"])
