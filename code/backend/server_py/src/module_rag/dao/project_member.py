from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_rag.do.project_member import (
    ProjectMember,
    ProjectMemberCreate,
    ProjectMemberUpdate,
    MyProjectResponse,
)
from module_rag.do.project import Project


class ProjectMemberDao:
    """项目成员数据访问对象"""

    @DaoRel
    async def add(
        self, member: ProjectMemberCreate, session: AsyncSession | None = None
    ) -> str:
        """
        新增项目成员记录
        :param member: 项目成员创建数据
        :param session: 可选数据库会话
        :return: 新创建项目成员的ID
        """
        db_member = ProjectMember.model_validate(member.model_dump(exclude_unset=True))
        session.add(db_member)
        await session.flush()
        return db_member.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除项目成员记录
        :param id: 要删除的项目成员ID
        :param session: 可选数据库会话
        """
        member = await session.get(ProjectMember, id)
        if not member:
            raise ValueError(f"未找到ID为 {id} 的项目成员")
        await session.delete(member)
        await session.flush()

    @DaoRel
    async def update(
        self,
        member_id: str,
        member: ProjectMemberUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新项目成员记录
        :param member_id: 要更新的项目成员ID
        :param member: 项目成员更新数据
        :param session: 可选数据库会话
        """
        update_data = member.model_dump(exclude_unset=True)
        stmt = update(ProjectMember).where(ProjectMember.id == member_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {member_id} 的项目成员")
        await session.flush()

    @DaoRel
    async def get(
        self, id: str, session: AsyncSession | None = None
    ) -> ProjectMember | None:
        """
        查询单个项目成员
        :param id: 要查询的项目成员ID
        :param session: 可选数据库会话
        :return: 项目成员对象，未找到返回None
        """
        return await session.get(ProjectMember, id)

    @DaoRel
    async def get_by_user_and_project(
        self, user_id: str, project_id: str, session: AsyncSession | None = None
    ) -> ProjectMember | None:
        """
        根据用户ID和项目ID查询成员关系
        :param user_id: 用户ID
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 项目成员对象，未找到返回None
        """
        statement = select(ProjectMember).where(
            ProjectMember.user_id == user_id,
            ProjectMember.project_id == project_id
        )
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def list_by_project(
        self, project_id: str, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[ProjectMember]:
        """
        分页查询项目的成员列表
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 项目成员列表
        """
        statement = (
            select(ProjectMember)
            .where(ProjectMember.project_id == project_id)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def delete_by_project(
        self,
        project_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """
        按项目ID批量删除成员记录(用于删除项目时级联清理)
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 删除的记录数
        """
        statement = select(ProjectMember).where(
            ProjectMember.project_id == project_id
        )
        result = await session.exec(statement)
        members = result.all()
        for m in members:
            await session.delete(m)
        await session.flush()
        return len(members)

    @DaoRel
    async def count_by_project(
        self, project_id: str, session: AsyncSession | None = None
    ) -> int:
        """
        获取项目成员总数
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 项目成员总数
        """
        statement = (
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id)
        )
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def list_my_projects(
        self, user_id: str, pagination: PaginationParams, session: AsyncSession | None = None
    ) -> list[MyProjectResponse]:
        """
        查询我参与的项目列表（用于前端展示"我参与的项目及我的身份"）
        :param user_id: 用户ID
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 项目列表，包含项目信息和角色
        """
        statement = (
            select(
                Project.id.label("project_id"),
                Project.name.label("project_name"),
                Project.description.label("project_description"),
                Project.is_private.label("is_private"),
                Project.kb_category.label("kb_category"),
                ProjectMember.role.label("role"),
                Project.created_at.label("created_at")
            )
            .join(ProjectMember, Project.id == ProjectMember.project_id)
            .where(ProjectMember.user_id == user_id)
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await session.exec(statement)
        rows = result.all()
        return [MyProjectResponse(**row._mapping) for row in rows]

    @DaoRel
    async def count_my_projects(
        self, user_id: str, session: AsyncSession | None = None
    ) -> int:
        """
        获取我参与的项目总数
        :param user_id: 用户ID
        :param session: 可选数据库会话
        :return: 项目总数
        """
        statement = (
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.user_id == user_id)
        )
        result = await session.exec(statement)
        return result.one()
