from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_rag.do.project import Project, ProjectCreate, ProjectUpdate, ProjectResponse, KbCategory
from module_rag.do.project_member import ProjectMemberCreate, RagRole
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_member import ProjectMemberDao
from module_rag.dao.project_dept import ProjectDeptDao
from module_rag.dao.project_document import ProjectDocumentDao
from common.config.path import DIR_UPLOAD
import logging
import shutil
from module_rag.dao.project_document_chunk import ProjectDocumentChunkDao
from module_file.service.filesystem import FileService

logger = logging.getLogger(__name__)

# 知识库模块在虚拟目录树中的模块根(source_module 标记 + 显示名)
RAG_MODULE_KEY = "rag"
RAG_MODULE_LABEL = "知识库"


async def ensure_project_folder(
    project_dao: ProjectDao,
    file_service: FileService,
    project_id: str,
    owner_user_id: str | None = None,
    session: AsyncSession | None = None,
) -> str:
    """确保项目根文件夹存在并回写 root_entry_id(幂等, 惰性补建; 项目服务与文档服务共用)

    虚拟目录: /知识库(rag模块根)/<项目名>(项目文件夹)
    :param project_dao: 项目DAO
    :param file_service: 统一文件服务
    :param project_id: 项目ID
    :param owner_user_id: 创建者用户ID(补建时的条目归属者)
    :param session: 可选数据库会话(由事务装饰器自动注入)
    :return: 项目根文件夹条目ID
    """
    # @DaoRel 方法由装饰器自动注入会话, 显式传 session=None 会与自动注入重复导致 TypeError;
    # 故仅在存在外部会话(共享事务)时透传, 为空时让各 DAO 自管事务
    extra: dict = {"session": session} if session else {}
    project = await project_dao.get(project_id, **extra)
    if not project:
        raise LookupError(f"项目 {project_id} 不存在")
    if project.root_entry_id:
        # 已关联的条目可能被外部删除 → 失效时重新补建
        entry = await file_service.get_file_entry(project.root_entry_id)
        if entry and entry.is_active:
            return project.root_entry_id
    # 幂等确保模块根与项目文件夹(重名残留直接复用)
    module_root = await file_service.ensure_module_root(
        RAG_MODULE_KEY, RAG_MODULE_LABEL, owner_user_id, **extra
    )
    folder = await file_service.ensure_folder(
        project.name, module_root.id, owner_user_id, **extra
    )
    if project.root_entry_id != folder.id:
        await project_dao.update(
            project_id, ProjectUpdate(root_entry_id=folder.id), **extra
        )
    return folder.id


class ProjectService:
    """项目服务

    条目级文件口径: 每个项目在虚拟目录树 /知识库/<项目名>/ 下拥有独立项目文件夹
    (file_entry, source_module='rag'), 项目文件夹下的子目录与文档由统一文件服务管理,
    文件管理模块可见但只读(业务条目拦截)。
    """

    def __init__(
        self,
        project_dao: ProjectDao | None = None,
        member_dao: ProjectMemberDao | None = None,
        document_dao: ProjectDocumentDao | None = None,
        project_document_chunk_dao: ProjectDocumentChunkDao  | None = None,
        dept_auth_dao: ProjectDeptDao | None = None,
        file_service: FileService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.project_dao = project_dao or ProjectDao()
        self.member_dao = member_dao or ProjectMemberDao()
        self.document_dao = document_dao or ProjectDocumentDao()
        self.project_document_chunk_dao = (
            project_document_chunk_dao or ProjectDocumentChunkDao()
        )
        self.dept_auth_dao = dept_auth_dao or ProjectDeptDao()
        # 统一文件存储服务(条目级: 项目文件夹/文档条目共用虚拟目录树)
        self.file_service = file_service or FileService()

    async def ensure_project_folder(
        self, project_id: str, owner_user_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> str:
        """确保项目根文件夹存在并回写 root_entry_id(委托模块级共用实现)"""
        return await ensure_project_folder(
            self.project_dao, self.file_service, project_id,
            owner_user_id=owner_user_id, session=session,
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
        同时在虚拟目录 /知识库/ 下创建项目根文件夹
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

        # 创建项目根文件夹(虚拟目录 /知识库/<项目名>/, 统一文件服务管理)
        await self.ensure_project_folder(
            project_id, owner_user_id=current_user_id, session=session
        )
        return project_id

    @DaoRel
    async def delete(self, project_id: str, session: AsyncSession | None = None):
        """
        删除项目(级联清理)
        - 删项目根文件夹(虚拟树递归删条目 + 释放内容引用)
        - 清理非条目口径文档的物理内容(旧数据兼容)
        - 清理 Milvus 向量 + 删项目所有文档/成员/部门授权记录
        - 删项目本身
        :param project_id: 项目ID
        :param session: 可选数据库会话(由事务装饰器自动注入)
        """
        project = await self.project_dao.get(project_id, session=session)

        # 1. 查所有文档(用于清理非条目口径的物理内容与向量)
        docs = await self.document_dao.list_all_by_project(
            project_id, session=session
        )

        # 2. 清理 Milvus 向量(按 project_id 批量删，容忍向量库未连接)
        await self.project_document_chunk_dao.vector_delete_by_project_id(project_id)

        # 3. 删项目根文件夹(条目级文档的内容引用随子树删除统一释放)
        if project and project.root_entry_id:
            try:
                await self.file_service.delete_folder(
                    project.root_entry_id, session=session
                )
            except Exception as e:
                logger.warning(f"删除项目文件夹失败 {project.root_entry_id}: {e}")

        # 4. 清理非条目口径文档的物理内容(内容级/本地文件旧数据兼容)
        for doc in docs:
            if doc.entry_id:
                # 条目级: 内容引用已随项目文件夹删除释放, 跳过避免重复扣减
                continue
            try:
                if doc.content_hash:
                    await self.file_service.release_content(
                        doc.content_hash, session=session
                    )
                    continue
                file_path = DIR_UPLOAD / doc.physical_path
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"删除物理文件失败 {doc.physical_path}: {e}")

        # 5. 删 db 文档记录
        deleted_docs = await self.document_dao.delete_by_project(
            project_id, session=session
        )
        logger.info(
            f"删除项目 {project_id}: 已清理 {deleted_docs} 个文档记录"
        )

        # 6. 删 db 成员记录
        deleted_members = await self.member_dao.delete_by_project(
            project_id, session=session
        )
        logger.info(
            f"删除项目 {project_id}: 已清理 {deleted_members} 个成员记录"
        )

        # 6.5 删 db 部门授权记录
        deleted_depts = await self.dept_auth_dao.delete_by_project(
            project_id, session=session
        )
        logger.info(
            f"删除项目 {project_id}: 已清理 {deleted_depts} 个部门授权记录"
        )

        # 7. 清理旧口径遗留的项目本地目录(历史数据兼容)
        project_dir = DIR_UPLOAD / project_id
        try:
            if project_dir.exists():
                shutil.rmtree(project_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"删除项目目录失败 {project_dir}: {e}")

        # 8. 删项目本身
        await self.project_dao.delete(project_id, session=session)

        logger.info(f"项目 {project_id} 删除完成")

    async def update(self, project_id: str, project: ProjectUpdate):
        """
        更新项目(名称变更时同步重命名虚拟目录中的项目文件夹)
        :param project_id: 项目ID
        :param project: 项目更新数据
        """
        if project.kb_category is not None and project.kb_category not in KbCategory.values():
            raise ValueError(
                f"无效的知识库分类 '{project.kb_category}'，允许的值: {'/'.join(KbCategory.values())}"
            )
        await self.project_dao.update(project_id, project)
        # 名称变更: 同步重命名项目根文件夹(失败仅告警,不影响项目更新)
        if project.name:
            db_project = await self.project_dao.get(project_id)
            if db_project and db_project.root_entry_id:
                try:
                    await self.file_service.rename(
                        db_project.root_entry_id, project.name
                    )
                except ValueError:
                    # 同名冲突等场景保留原文件夹名(虚拟目录名与项目名短暂不一致可接受)
                    logger.warning(
                        f"项目文件夹重命名失败(可能同名) project={project_id}"
                    )

    async def get(self, project_id: str) -> Project | None:
        """
        获取项目详情
        :param project_id: 项目ID
        :return: 项目对象
        """
        return await self.project_dao.get(project_id)

    async def list_paged(
        self, pagination: PaginationParams, kb_category: str | None = None,
        name: str | None = None, is_private: bool | None = None,
    ) -> PaginationResponse:
        """
        分页获取项目列表(支持多字段过滤)
        :param pagination: 分页参数
        :param kb_category: 可选知识库分类过滤(personal/project/company)
        :param name: 项目名称模糊匹配
        :param is_private: 可选私有状态过滤(true=私有/false=公开)
        :return: 分页项目列表
        """
        items = await self.project_dao.list_paged(
            pagination, name=name, kb_category=kb_category, is_private=is_private
        )
        total = await self.project_dao.count(
            name=name, kb_category=kb_category, is_private=is_private
        )
        return PaginationResponse.create(items, total, pagination)
