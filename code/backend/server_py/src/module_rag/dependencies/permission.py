"""
项目级权限校验(基于成员表固定档位,不走 casbin 项目域)

设计(GitHub 式):
    角色存 project_member.role,固定三档,数值越大权限越高:
        project_reader(1)  仅只读
        project_editor(2)  读 + 写(上传/修改/对话)
        project_admin(3)   全部(删除/成员管理)

    鉴权规则:
        1. 全局管理员(casbin 全局域 admin)穿透所有项目权限
        2. 项目成员按档位比较: 动作所需档位 <= 成员档位 即放行
        3. 公开项目(非私有)允许任何登录用户只读
"""
from fastapi import Depends, HTTPException, status

from module_authorization.config.casbin_rule import auth_manager
from module_authorization.dependencies.auth import get_current_user_id
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.do.project_member import RagRole

# 各动作所需档位(未列出的动作按最高档 3 从严处理)
ACTION_LEVELS: dict[str, int] = {
    "read": 1,
    "upload": 2,
    "update": 2,
    "write": 2,
    "delete": 3,
    "invite": 3,
    "remove": 3,
    "manage": 3,
}


async def check_project_permission(
    user_id: str, project_id: str, obj: str, act: str
) -> bool:
    """
    项目级权限检查(不抛异常)
    :param user_id: 用户ID
    :param project_id: 项目ID
    :param obj: 资源对象(project/doc/member/chat)
    :param act: 动作
    :return: 是否有权限
    """
    # 1. 全局管理员穿透(casbin 全局域 admin 绑定)
    enforcer = auth_manager.enforcer
    if enforcer is not None and enforcer.has_grouping_policy(user_id, "admin", "*"):
        return True

    # 2. 项目成员按档位判断
    member = await ProjectMemberDao().get_by_user_and_project(user_id, project_id)
    if member is not None:
        required = ACTION_LEVELS.get(act, 3)
        return RagRole.level(member.role) >= required

    # 3. 公开项目允许任何登录用户只读
    if act == "read":
        project = await ProjectDao().get(project_id)
        if project is not None and not project.is_private:
            return True
    return False


async def enforce_project_permission(
    user_id: str, project_id: str, obj: str, act: str
) -> None:
    """
    项目级权限检查(无权限时抛出403)
    :param user_id: 用户ID
    :param project_id: 项目ID
    :param obj: 资源对象
    :param act: 动作
    """
    if not await check_project_permission(user_id, project_id, obj, act):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"无项目操作权限: {project_id}/{obj}/{act}",
        )


def require_project_permission(obj: str, act: str):
    """
    项目级权限校验依赖工厂
    要求路由路径包含 {project_id} 占位符
    :param obj: 资源对象
    :param act: 动作
    """
    async def dependency(
        project_id: str,
        current_user_id: str = Depends(get_current_user_id),
    ) -> str:
        await enforce_project_permission(current_user_id, project_id, obj, act)
        return current_user_id

    return dependency
