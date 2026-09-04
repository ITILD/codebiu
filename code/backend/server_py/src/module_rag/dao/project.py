from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate


class ProjectDao:
    """项目数据访问对象"""

    @DaoRel
    async def add(
        self, project: Project, session: AsyncSession | None = None
    ) -> str:
        """
        新增项目记录
        :param project: 项目数据库对象(包含 created_by)
        :param session: 可选数据库会话
        :return: 新创建项目的ID
        """
        session.add(project)
        await session.flush()
        return project.id

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除项目记录
        :param id: 要删除的项目ID
        :param session: 可选数据库会话
        """
        project = await session.get(Project, id)
        if not project:
            raise ValueError(f"未找到ID为 {id} 的项目")
        await session.delete(project)
        await session.flush()

    @DaoRel
    async def update(
        self,
        project_id: str,
        project: ProjectUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新项目记录
        :param project_id: 要更新的项目ID
        :param project: 项目更新数据
        :param session: 可选数据库会话
        """
        update_data = project.model_dump(exclude_unset=True)
        stmt = update(Project).where(Project.id == project_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {project_id} 的项目")
        await session.flush()

    @DaoRel
    async def get(self, id: str, session: AsyncSession | None = None) -> Project | None:
        """
        查询单个项目
        :param id: 要查询的项目ID
        :param session: 可选数据库会话
        :return: 项目对象，未找到返回None
        """
        return await session.get(Project, id)

    @DaoRel
    async def list_paged(
        self, pagination: PaginationParams, session: AsyncSession | None = None,
        name: str | None = None,
        kb_category: str | None = None,
        is_private: bool | None = None,
    ) -> list[Project]:
        """
        分页查询项目列表(支持多字段过滤)
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :param name: 项目名称模糊匹配
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :param is_private: 可选私有状态过滤(true=私有/false=公开)
        :return: 项目列表
        """
        conditions = []
        if name:
            conditions.append(Project.name.contains(name))
        if kb_category is not None:
            conditions.append(Project.kb_category == kb_category)
        if is_private is not None:
            conditions.append(Project.is_private == is_private)

        statement = select(Project)
        if conditions:
            statement = statement.where(*conditions)
        statement = statement.offset(pagination.offset).limit(pagination.limit)
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count(
        self, session: AsyncSession | None = None,
        name: str | None = None,
        kb_category: str | None = None,
        is_private: bool | None = None,
    ) -> int:
        """
        获取项目总数(与列表过滤条件保持一致)
        :param session: 可选数据库会话
        :param name: 项目名称模糊匹配
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :param is_private: 可选私有状态过滤(true=私有/false=公开)
        :return: 项目总数
        """
        conditions = []
        if name:
            conditions.append(Project.name.contains(name))
        if kb_category is not None:
            conditions.append(Project.kb_category == kb_category)
        if is_private is not None:
            conditions.append(Project.is_private == is_private)

        statement = select(func.count()).select_from(Project)
        if conditions:
            statement = statement.where(*conditions)
        result = await session.exec(statement)
        return result.one()
