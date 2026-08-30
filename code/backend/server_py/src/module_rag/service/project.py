from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse, KbCategory
from module_rag.do.project_member import ProjectMemberCreate, RagRole
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.dao.project_document import ProjectDocumentDao
from common.config.path import DIR_UPLOAD
import logging
import shutil
from module_rag.dao.project_document_chunk import ProjectDocumentChunkDao

logger = logging.getLogger(__name__)


class ProjectService:
    """项目服务"""

    def __init__(
        self,
        project_dao: ProjectDao | None = None,
        member_dao: ProjectMemberDao | None = None,
        document_dao: ProjectDocumentDao | None = None,
        project_document_chunk_dao: ProjectDocumentChunkDao  | None = None,
    ):
        self.project_dao = project_dao or ProjectDao()
        self.member_dao = member_dao or ProjectMemberDao()
        self.document_dao = document_dao or ProjectDocumentDao()
        self.project_document_chunk_dao = (
            project_document_chunk_dao or ProjectDocumentChunkDao()
        )

    @DaoRel
    async def add(
        self,
        project: ProjectCreate,
        current_user_id: str,
        session: AsyncSession | None = None,
    ) -> str:
        """
        创建项目，并自动将当前用户设为项目管理员(原子事务)
        :param project: 项目创建数据(不含 created_by)
        :param current_user_id: 当前登录用户ID(由系统从 token 获取)
        :param session: 可选数据库会话(由事务装饰器自动注入)
        :return: 创建的项目ID
        """
        # 校验知识库分类合法性
        if project.kb_category not in KbCategory.values():
            raise ValueError(
                f"无效的知识库分类 '{project.kb_category}'，允许的值: {'/'.join(KbCategory.values())}"
            )
        # 构造数据库对象，后端设置 created_by
        db_project = Project(
            **project.model_dump(),
            created_by=current_user_id,
        )
        project_id = await self.project_dao.add(db_project, session=session)

        # 自动将创建者添加为项目管理员
        member = ProjectMemberCreate(
            user_id=current_user_id,
            project_id=project_id,
            role=RagRole.PROJECT_ADMIN,
        )
        await self.member_dao.add(member, session=session)

        # 同步 casbin 角色绑定(域 rag:{project_id}),创建者为项目管理员
        from module_authorization.dependencies.permission import (
            sync_project_member_role,
        )
        await sync_project_member_role(
            current_user_id, project_id, RagRole.PROJECT_ADMIN
        )
        return project_id

    @DaoRel
    async def delete(self, project_id: str, session: AsyncSession | None = None):
        """
        删除项目(级联清理)
        - 先查所有文档 → 删物理文件 + 删 Milvus 向量
        - 删项目所有文档 db 记录
        - 删项目所有成员
        - 删项目上传目录
        - 删项目本身
        :param project_id: 项目ID
        :param session: 可选数据库会话(由事务装饰器自动注入)
        """
        # 1. 查所有文档(用于清理物理文件和向量)
        docs = await self.document_dao.list_all_by_project(
            project_id, session=session
        )

        # 2. 清理 Milvus 向量(按 project_id 批量删，容忍向量库未连接)
        await self.project_document_chunk_dao.vector_delete_by_project_id(project_id)
        # 3. 清理物理文件(逐个删，再删整个目录)
        for doc in docs:
            try:
                file_path = DIR_UPLOAD / doc.physical_path
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"删除物理文件失败 {doc.physical_path}: {e}")

        # 4. 删 db 文档记录
        deleted_docs = await self.document_dao.delete_by_project(
            project_id, session=session
        )
        logger.info(
            f"删除项目 {project_id}: 已清理 {deleted_docs} 个文档记录"
        )

        # 5. 删 db 成员记录
        deleted_members = await self.member_dao.delete_by_project(
            project_id, session=session
        )
        logger.info(
            f"删除项目 {project_id}: 已清理 {deleted_members} 个成员记录"
        )

        # 6. 删项目上传目录
        project_dir = DIR_UPLOAD / project_id
        try:
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"删除项目目录失败 {project_dir}: {e}")

        # 7. 删项目本身
        await self.project_dao.delete(project_id, session=session)

        # 8. 清理 casbin 项目域(rag:{project_id})下的全部角色绑定
        from module_authorization.dependencies.permission import remove_project_roles
        await remove_project_roles(project_id)
        logger.info(f"项目 {project_id} 删除完成")

    async def update(self, project_id: str, project: ProjectUpdate):
        """
        更新项目
        :param project_id: 项目ID
        :param project: 项目更新数据
        """
        if project.kb_category is not None and project.kb_category not in KbCategory.values():
            raise ValueError(
                f"无效的知识库分类 '{project.kb_category}'，允许的值: {'/'.join(KbCategory.values())}"
            )
        await self.project_dao.update(project_id, project)

    async def get(self, project_id: str) -> Project | None:
        """
        获取项目详情
        :param project_id: 项目ID
        :return: 项目对象
        """
        return await self.project_dao.get(project_id)

    async def list_all(
        self, pagination: PaginationParams, kb_category: str | None = None
    ) -> PaginationResponse:
        """
        分页获取项目列表
        :param pagination: 分页参数
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :return: 分页项目列表
        """
        items = await self.project_dao.list_all(pagination, kb_category=kb_category)
        total = await self.project_dao.count(kb_category=kb_category)
        return PaginationResponse.create(items, total, pagination)
