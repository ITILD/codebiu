from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.utils.db.schema.pagination import PaginationParams
from common.config.db import DaoRel,db_vector
from module_rag.do.project_document import (
    ProjectDocument,
    ProjectDocumentCreate,
    ProjectDocumentUpdate
)

class ProjectDocumentDao:
    """项目文档数据访问对象"""

    @DaoRel
    async def add(
        self,
        document: ProjectDocumentCreate,
        session: AsyncSession | None = None,
    ) -> ProjectDocument:
        """
        新增项目文档记录
        :param document: 项目文档创建数据
        :param session: 可选数据库会话
        :return: 新创建文档的对象
        """
        db_document = ProjectDocument.model_validate(
            document.model_dump(exclude_unset=True)
        )
        session.add(db_document)
        await session.flush()
        return db_document

    @DaoRel
    async def delete(self, id: str, session: AsyncSession | None = None):
        """
        删除项目文档记录
        :param id: 要删除的文档ID
        :param session: 可选数据库会话
        """
        document = await session.get(ProjectDocument, id)
        if not document:
            raise ValueError(f"未找到ID为 {id} 的文档")
        await session.delete(document)
        await session.flush()

    @DaoRel
    async def update(
        self,
        document_id: str,
        document: ProjectDocumentUpdate,
        session: AsyncSession | None = None,
    ):
        """
        更新项目文档记录
        :param document_id: 要更新的文档ID
        :param document: 文档更新数据
        :param session: 可选数据库会话
        """
        update_data = document.model_dump(exclude_unset=True)
        stmt = (
            update(ProjectDocument)
            .where(ProjectDocument.id == document_id)
            .values(**update_data)
        )
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise ValueError(f"未找到ID为 {document_id} 的文档")
        await session.flush()

    @DaoRel
    async def get(
        self, id: str, session: AsyncSession | None = None
    ) -> ProjectDocument | None:
        """
        查询单个项目文档
        :param id: 要查询的文档ID
        :param session: 可选数据库会话
        :return: 文档对象，未找到返回None
        """
        return await session.get(ProjectDocument, id)

    @DaoRel
    async def list_by_project(
        self,
        project_id: str,
        pagination: PaginationParams,
        session: AsyncSession | None = None,
    ) -> list[ProjectDocument]:
        """
        分页查询项目的文档列表
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param session: 可选数据库会话
        :return: 文档列表
        """
        statement = (
            select(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
            .offset(pagination.offset)
            .limit(pagination.limit)
            .order_by(ProjectDocument.created_at.desc())
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def list_all_by_project(
        self,
        project_id: str,
        session: AsyncSession | None = None,
    ) -> list[ProjectDocument]:
        """
        查询项目的全部文档列表(不分页，用于批量删除场景)
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 文档列表
        """
        statement = (
            select(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
            .order_by(ProjectDocument.created_at.desc())
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
        按项目ID批量删除文档记录(物理文件与向量需由 service 层单独清理)
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 删除的记录数
        """
        statement = (
            select(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
        )
        result = await session.exec(statement)
        docs = result.all()
        for doc in docs:
            await session.delete(doc)
        await session.flush()
        return len(docs)

    @DaoRel
    async def count_by_project(
        self, project_id: str, session: AsyncSession | None = None
    ) -> int:
        """
        获取项目文档总数
        :param project_id: 项目ID
        :param session: 可选数据库会话
        :return: 文档总数
        """
        statement = (
            select(func.count())
            .select_from(ProjectDocument)
            .where(ProjectDocument.project_id == project_id)
        )
        result = await session.exec(statement)
        return result.one()