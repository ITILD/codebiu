from fastapi import APIRouter, HTTPException, status, Depends, Query
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_dept import (
    ProjectDeptCreate,
    ProjectDeptUpdate,
    ProjectDeptResponse,
)
from module_rag.service.project_dept import ProjectDeptService
from module_rag.dependencies.project_dept import get_project_dept_service
from module_rag.dependencies.permission import (
    enforce_project_permission,
    require_project_permission,
)
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.service.dept import DeptService
from module_authorization.dependencies.dept import get_dept_service
from module_rag.config.server import module_app

router = APIRouter()


@router.get(
    "/dept-tree", summary="获取部门树(供项目授权选择,仅需登录)", response_model=list
)
async def get_dept_tree_for_auth(
    service: DeptService = Depends(get_dept_service),
):
    """
    获取部门树(供知识库项目授权选择使用)

    与 /authorization/depts/tree 不同: 本端点仅需登录,不要求 sys:dept:read 权限码,
    使普通项目管理员(知识库创建者)也能按部门授权
    """
    try:
        return await service.get_tree()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post(
    "", summary="添加部门授权", status_code=status.HTTP_201_CREATED, response_model=str
)
async def add_project_dept(
    dept_auth: ProjectDeptCreate,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDeptService = Depends(get_project_dept_service),
):
    """
    添加项目部门授权(需要该知识库的成员邀请权限)
    :param dept_auth: 部门授权数据(role 必须为 project_admin/project_editor/project_reader 之一)
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 部门授权服务依赖注入
    :return: 创建的授权记录ID
    """
    # 邀请权限校验(复用成员管理的 invite 档位)
    await enforce_project_permission(
        current_user_id, dept_auth.project_id, "member", "invite"
    )
    try:
        return await service.add(dept_auth)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/project/{project_id}", summary="获取项目部门授权列表", response_model=PaginationResponse
)
async def list_project_depts(
    project_id: str,
    pagination: PaginationParams = Depends(),
    role: str | None = Query(None, description="授权档位过滤(project_admin/project_editor/project_reader)"),
    current_user_id: str = Depends(require_project_permission("member", "read")),
    service: ProjectDeptService = Depends(get_project_dept_service),
):
    """
    获取项目部门授权列表(支持档位过滤)
    :param project_id: 项目ID
    :param pagination: 分页参数
    :param role: 授权档位过滤
    :param current_user_id: 当前登录用户ID(由项目读权限依赖校验)
    :param service: 部门授权服务依赖注入
    :return: 分页授权列表
    """
    try:
        return await service.list_by_project(project_id, pagination, role=role)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put(
    "/{id}", summary="更新部门授权档位", response_model=ProjectDeptResponse
)
async def update_project_dept(
    id: str,
    dept_auth: ProjectDeptUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDeptService = Depends(get_project_dept_service),
):
    """
    更新部门授权档位(需要该知识库的成员管理权限)
    :param id: 授权记录ID
    :param dept_auth: 更新数据
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 部门授权服务依赖注入
    :return: 更新后的授权记录
    """
    # 先查授权记录以获取 project_id 做权限校验
    auth_info = await service.get(id)
    if not auth_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="部门授权未找到"
        )
    await enforce_project_permission(
        current_user_id, auth_info.project_id, "member", "update"
    )
    try:
        await service.update(id, dept_auth)
        return await service.get(id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete(
    "/{id}", summary="移除部门授权", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_project_dept(
    id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: ProjectDeptService = Depends(get_project_dept_service),
):
    """
    移除部门授权(需要该知识库的成员移除权限)
    :param id: 授权记录ID
    :param current_user_id: 当前登录用户ID(由 token 自动解析)
    :param service: 部门授权服务依赖注入
    """
    # 先查授权记录以获取 project_id 做权限校验
    auth_info = await service.get(id)
    if not auth_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="部门授权未找到"
        )
    await enforce_project_permission(
        current_user_id, auth_info.project_id, "member", "remove"
    )
    try:
        await service.delete(id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# 注册路由
module_app.include_router(router, prefix="/project-depts", tags=["项目部门授权"])
