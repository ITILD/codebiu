from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project_member import (
    ProjectMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    ProjectMemberResponse,
    MyProjectResponse,
)
from module_rag.dao.project_member import ProjectMemberDao
import logging

logger = logging.getLogger(__name__)


class ProjectMemberService:
    """项目成员服务(角色存成员表,项目内鉴权按档位判断,见 dependencies/permission.py)"""

    def __init__(self, member_dao: ProjectMemberDao):
        self.member_dao = member_dao or ProjectMemberDao()

    async def add(self, member: ProjectMemberCreate) -> str:
        """
        添加项目成员
        :param member: 项目成员创建数据
        :return: 创建的项目成员ID
        """
        existing = await self.member_dao.get_by_user_and_project(member.user_id, member.project_id)
        if existing:
            raise ValueError(f"用户 {member.user_id} 已是项目 {member.project_id} 的成员")
        return await self.member_dao.add(member)

    async def delete(self, member_id: str):
        """
        移除项目成员
        :param member_id: 项目成员ID
        """
        await self.member_dao.delete(member_id)

    async def update(self, member_id: str, member: ProjectMemberUpdate):
        """
        更新项目成员角色
        :param member_id: 项目成员ID
        :param member: 项目成员更新数据
        """
        await self.member_dao.update(member_id, member)

    async def get(self, member_id: str) -> ProjectMember | None:
        """
        获取项目成员详情
        :param member_id: 项目成员ID
        :return: 项目成员对象
        """
        return await self.member_dao.get(member_id)

    async def list_by_project(
        self, project_id: str, pagination: PaginationParams,
        role: str | None = None,
        user_keyword: str | None = None,
    ) -> PaginationResponse:
        """
        分页获取项目成员列表(支持角色/用户关键字过滤)
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param role: 项目角色精确过滤(owner/admin/editor/viewer)
        :param user_keyword: 用户名/昵称模糊过滤
        :return: 分页项目成员列表
        """
        items = await self.member_dao.list_by_project(
            project_id, pagination, role=role, user_keyword=user_keyword
        )
        total = await self.member_dao.count_by_project(
            project_id, role=role, user_keyword=user_keyword
        )
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
