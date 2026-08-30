from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_member import (
    ProjectMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    MyProjectResponse,
)
from module_rag.dao.project_member import ProjectMemberDao
from module_authorization.dependencies.permission import sync_project_member_role
import logging

logger = logging.getLogger(__name__)


class ProjectMemberService:
    """项目成员服务(成员记录与 casbin 域角色双写,实现同知识库多用户配置)"""

    def __init__(self, member_dao: ProjectMemberDao):
        self.member_dao = member_dao or ProjectMemberDao()

    async def add(self, member: ProjectMemberCreate) -> str:
        """
        添加项目成员(同步授予 casbin 项目域角色 rag:{project_id})
        :param member: 项目成员创建数据
        :return: 创建的项目成员ID
        """
        existing = await self.member_dao.get_by_user_and_project(member.user_id, member.project_id)
        if existing:
            raise ValueError(f"用户 {member.user_id} 已是项目 {member.project_id} 的成员")
        member_id = await self.member_dao.add(member)
        # 同步 casbin 角色绑定
        await sync_project_member_role(
            member.user_id, member.project_id, member.role
        )
        return member_id

    async def delete(self, member_id: str):
        """
        移除项目成员(同步撤销 casbin 项目域角色)
        :param member_id: 项目成员ID
        """
        member = await self.member_dao.get(member_id)
        await self.member_dao.delete(member_id)
        if member:
            # 撤销该项目域下该用户的角色
            await sync_project_member_role(
                member.user_id, member.project_id, None, old_role=member.role
            )

    async def update(self, member_id: str, member: ProjectMemberUpdate):
        """
        更新项目成员角色(同步变更 casbin 项目域角色)
        :param member_id: 项目成员ID
        :param member: 项目成员更新数据
        """
        old = await self.member_dao.get(member_id)
        await self.member_dao.update(member_id, member)
        if old and member.role is not None and member.role != old.role:
            # 角色变更: 先移除旧角色再授予新角色
            await sync_project_member_role(
                old.user_id, old.project_id, member.role, old_role=old.role
            )

    async def get(self, member_id: str) -> ProjectMember | None:
        """
        获取项目成员详情
        :param member_id: 项目成员ID
        :return: 项目成员对象
        """
        return await self.member_dao.get(member_id)

    async def list_by_project(
        self, project_id: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """
        分页获取项目成员列表
        :param project_id: 项目ID
        :param pagination: 分页参数
        :return: 分页项目成员列表
        """
        items = await self.member_dao.list_by_project(project_id, pagination)
        total = await self.member_dao.count_by_project(project_id)
        return PaginationResponse.create(items, total, pagination)

    async def list_my_projects(
        self, user_id: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """
        获取我参与的项目列表（前端展示"我参与的项目及我的身份"）
        :param user_id: 用户ID
        :param pagination: 分页参数
        :return: 分页项目列表
        """
        items = await self.member_dao.list_my_projects(user_id, pagination)
        total = await self.member_dao.count_my_projects(user_id)
        return PaginationResponse.create(items, total, pagination)
