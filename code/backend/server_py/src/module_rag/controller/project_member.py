from fastapi import APIRouter, HTTPException, status, Depends, Query
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_member import (
    ProjectMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    MyProjectResponse,
    RagRole,
)
from module_rag.service.project_member import ProjectMemberService
from module_rag.dependencies.project_member import get_project_member_service
from module_rag.dependencies.permission import (
    enforce_project_permission,
    require_project_permission,
)
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.config.server import module_app

router = APIRouter()

@router.post(
    "", summary="添加项目成员", status_code=status.HTTP_201_CREATED, response_model=str
)
async def add_project_member(
    member: ProjectMemberCreate,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    添加项目成员(需要该知识库的成员邀请权限)
    :param member: 项目成员数据(role 必须为 project_admin/project_editor/project_reader 之一)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 项目成员服务依赖注入
    :return: 创建的项目成员ID
    """
    # 角色合法性校验(仅允许分配项目级角色)
    if member.role not in RagRole.PROJECT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色 '{member.role}'，允许的角色: {'/'.join(RagRole.PROJECT_ROLES)}",
        )
    # 邀请权限校验(域 rag:{project_id})
    await enforce_project_permission(
        current_user_id, member.project_id, "member", "invite"
    )
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
    "/my", summary="获取我参与的项目", response_model=PaginationResponse
)
async def list_my_projects(
    pagination: PaginationParams = Depends(),
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    获取我参与的项目列表（前端展示"我参与的项目及我的身份"）
    :param pagination: 分页参数
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 项目成员服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_my_projects(current_user_id, pagination)
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
    role: str | None = Query(None, description="项目角色过滤(owner/admin/editor/viewer)"),
    user_keyword: str | None = Query(None, max_length=50, description="用户名/昵称模糊搜索"),
    current_user_id: str = Depends(require_project_permission("member", "read")),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    获取项目成员列表(支持角色/用户关键字过滤)
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param role: 项目角色过滤(owner/admin/editor/viewer)
    :param user_keyword: 用户名/昵称模糊搜索(联表用户表)
    :param service: 项目成员服务依赖注入
    :return: 分页响应结果
    """
    try:
        return await service.list_by_project(
            project_id, pagination, role=role, user_keyword=user_keyword
        )
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
    except HTTPException:
        # 保留 404 语义,避免被包装成 500
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{member_id}", summary="移除项目成员", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_project_member(
    member_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    移除项目成员(需要该知识库的成员移除权限)
    :param member_id: 项目成员ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 项目成员服务依赖注入
    """
    # 先查成员记录以获取 project_id 做权限校验
    member_info = await service.get(member_id)
    if not member_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目成员未找到"
        )
    await enforce_project_permission(
        current_user_id, member_info.project_id, "member", "remove"
    )
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
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectMemberService = Depends(get_project_member_service)
):
    """
    更新项目成员角色(需要该知识库的成员管理权限)
    :param member_id: 项目成员ID
    :param member: 项目成员更新数据(role 必须为 project_admin/project_editor/project_reader 之一)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 项目成员服务依赖注入
    """
    # 角色合法性校验(仅允许分配项目级角色)
    if member.role is not None and member.role not in RagRole.PROJECT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色 '{member.role}'，允许的角色: {'/'.join(RagRole.PROJECT_ROLES)}",
        )
    # 先查成员记录以获取 project_id 做权限校验
    member_info = await service.get(member_id)
    if not member_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目成员未找到"
        )
    await enforce_project_permission(
        current_user_id, member_info.project_id, "member", "update"
    )
    try:
        await service.update(member_id, member)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/project-members", tags=["项目成员管理"])
