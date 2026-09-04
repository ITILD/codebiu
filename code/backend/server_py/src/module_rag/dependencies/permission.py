"""
项目级权限校验(基于成员表固定档位 + 部门授权,不走 casbin 项目域)

设计(GitHub 式):
    角色存 project_member.role(直连成员)与 project_dept.role(部门授权),
    固定三档,数值越大权限越高:
        project_reader(1)  仅只读
        project_editor(2)  读 + 写(上传/修改/对话)
        project_admin(3)   全部(删除/成员管理/部门授权)

    鉴权规则:
        1. 全局管理员(casbin 全局域 admin)穿透所有项目权限
        2. 生效档位 = max(直连成员档位, 部门授权档位),达到动作所需档位即放行
           部门授权级联: 用户所在部门的 ancestors 祖级链 + 自身 命中授权记录即生效
        3. 公开项目(非私有)允许任何登录用户只读
"""
from fastapi import Depends, HTTPException, status

from module_authorization.config.casbin_rule import auth_manager
from module_authorization.dependencies.auth import get_current_user_id
from module_authorization.dao.user import UserDao
from module_authorization.dao.dept import DeptDao
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.dao.project_dept import ProjectDeptDao
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


async def get_user_dept_chain(user_id: str) -> list[str]:
    """
    获取用户所在部门及其全部祖级部门ID(用于部门授权级联继承)
    :param user_id: 用户ID
    :return: 部门链ID列表(祖级链去根占位"0" + 自身);用户无部门返回空列表
    """
    user = await UserDao().get(user_id)
    if user is None or not user.dept_id:
        return []
    dept = await DeptDao().get_raw(user.dept_id)
    if dept is None:
        return []
    chain = [d for d in (dept.ancestors or "").split(",") if d and d != "0"]
    chain.append(dept.id)
    return chain


async def get_dept_role_level(user_id: str, project_id: str) -> int:
    """
    获取用户的部门授权档位(部门链命中授权的最高档)
    :param user_id: 用户ID
    :param project_id: 项目ID
    :return: 命中的最高档位数值,无命中返回 0
    """
    chain = await get_user_dept_chain(user_id)
    if not chain:
        return 0
    roles = await ProjectDeptDao().list_roles_by_dept_ids(project_id, chain)
    return max((RagRole.level(r) for r in roles), default=0)


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

    # 2. 生效档位 = max(直连成员档位, 部门授权档位)
    required = ACTION_LEVELS.get(act, 3)
    member_level = 0
    member = await ProjectMemberDao().get_by_user_and_project(user_id, project_id)
    if member is not None:
        member_level = RagRole.level(member.role)
    dept_level = await get_dept_role_level(user_id, project_id)
    if max(member_level, dept_level) >= required:
        return True

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
