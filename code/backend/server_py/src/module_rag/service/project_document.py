import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path

import aiofiles
from fastapi import HTTPException
from langchain.chat_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings

from common.config.db import db_vector
from common.utils.fastapiEX.exceptions import NotFoundError
from common.config.path import DIR_UPLOAD
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from module_ai.service.llm_base import LLMBaseService
from module_ai.service.model_config import ModelConfigService
from module_ai.utils.llm.do.llm_type import ModelType
from module_file.do.filesystem import (
    EntryCreateRequest,
    FileEntry,
    FileEntryUpdate,
    MultipartCompleteRequest,
    MultipartInitRequest,
    MultipartInitResponse,
)
from module_file.service.filesystem import FileService
from module_office.service.document_chunk import DocumentChunkService
from module_office.service.document_parse import DocumentParseService
from module_office.utils.document_chunk.do.chunk import (
    ChunkConfig,
    ChunkStrategyEnum,
    ChunkStrategyRecommendation,
    ChunkedItem,
)
from module_office.utils.file_parase.do.chunk import Chunk
from module_rag.dao.project import ProjectDao
from module_rag.dao.project_document import ProjectDocumentDao
from module_rag.do.project_document import (
    DocType,
    IngestProgressCallback,
    IngestStep,
    IngestStepState,
    ParseStatus,
    ProjectDocument,
    ProjectDocumentCreate,
    ProjectDocumentUpdate,
    compute_ingest_progress,
)
from module_rag.do.project_document_chunk import ProjectDocumentChunk
from module_rag.service.project import ensure_project_folder
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_rag.service.user_model import UserModelService

logger = logging.getLogger(__name__)

# 单块读取大小(64KB)
_CHUNK_SIZE = 1024 * 64

# 解析所需模型类型的中文名(预检告警文案用)
_MODEL_TYPE_LABELS: dict[ModelType, str] = {
    ModelType.CHAT: "对话(LLM)",
    ModelType.EMBEDDINGS: "向量化(Embedding)",
}


class ProjectDocumentService:
    """项目文档服务：文件经统一文件存储流程上传(内容哈希去重/分片/预签名直传),
    project_document 作为知识库独立口径记录; 处理下载/删除/解析及元数据管理"""
    # service 需要对接task任务队列，不要抛http的错

    def __init__(
        self,
        document_dao: ProjectDocumentDao,
        project_dao: ProjectDao,
        user_model_service: UserModelService | None = None,
        llm_base_service: LLMBaseService | None = None,
        model_config_service: ModelConfigService | None = None,
        document_parse_service: DocumentParseService | None = None,
        document_chunk_service: DocumentChunkService | None = None,
        project_document_chunk_service: ProjectDocumentChunkService | None = None,
        file_service: FileService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.document_dao = document_dao or ProjectDocumentDao()
        self.project_dao = project_dao or ProjectDao()
        self.user_model_service = user_model_service or UserModelService()
        self.llm_base_service = llm_base_service or LLMBaseService()
        self.model_config_service = model_config_service or ModelConfigService()
        self.document_parse_service = document_parse_service or DocumentParseService()
        # 负责文档分块策略选择和分块操作
        self.document_chunk_service = document_chunk_service or DocumentChunkService()

        self.project_document_chunk_service = project_document_chunk_service or ProjectDocumentChunkService()

        # 统一文件存储服务(内容去重/分片会话/预签名/引用计数, 与文件管理共用一套存储)
        self.file_service = file_service or FileService()

    async def ensure_parse_models(self, user_id: str) -> list[str]:
        """校验文档解析所需模型(对话+向量化)是否可用(任务派发前预检)
        :param user_id: 当前用户ID(以其绑定的模型执行)
        :return: 缺失模型中文名列表(为空表示全部可用)
        """
        missing = await self.user_model_service.get_missing_model_types(
            user_id, (ModelType.CHAT, ModelType.EMBEDDINGS)
        )
        return [_MODEL_TYPE_LABELS[t] for t in missing]

    async def validate_upload(self, project_id: str, filename: str) -> str:
        """上传前置校验(直传/分片/秒传共用): 项目存在 + 文件类型允许
        :param project_id: 项目ID
        :param filename: 文件名
        :return: 小写扩展名(不含点)
        :raises NotFoundError: 项目不存在
        :raises ValueError: 文件名非法/类型不允许
        """
        project = await self.project_dao.get(project_id)
        if not project:
            logger.error(f"项目 {project_id} 不存在")
            raise NotFoundError(f"项目 {project_id} 不存在")
        if not filename:
            raise ValueError("文件名不能为空")
        ext = Path(filename).suffix.lstrip(".").lower()
        if not DocType.is_allowed_extension(ext):
            raise ValueError(
                f"不支持的文件类型 '{ext}'，允许: {'/'.join(DocType.ALLOWED_EXTENSIONS)}"
            )
        return ext

    async def _register_document_from_entry(
        self,
        *,
        project_id: str,
        entry: FileEntry,
        description: str | None,
        uploaded_by: str,
    ) -> ProjectDocument:
        """条目级落库: 统一文件服务已创建 file_entry(内容引用由条目维护),
        project_document 仅记录知识库口径元数据并关联 entry_id"""
        document_create = ProjectDocumentCreate(
            project_id=project_id,
            name=entry.name,
            file_extension=entry.file_extension or "",
            mime_type=entry.mime_type,
            file_size_bytes=entry.file_size_bytes or 0,
            physical_path=entry.logical_path,
            content_hash=entry.content_hash,
            entry_id=entry.id,
            description=description,
            uploaded_by=uploaded_by,
        )
        return await self.document_dao.add(document_create)

    async def _ensure_project_folder(
        self, project_id: str, owner_user_id: str | None = None
    ) -> str:
        """确保项目根文件夹存在(虚拟目录 /知识库/<项目名>/)并返回条目ID"""
        return await ensure_project_folder(
            self.project_dao, self.file_service, project_id,
            owner_user_id=owner_user_id,
        )

    async def _validate_folder_in_project(
        self, root_entry: FileEntry, folder_id: str
    ) -> FileEntry:
        """校验目标目录属于当前项目子树(防跨项目/跨模块越权操作)
        :param root_entry: 项目根文件夹条目
        :param folder_id: 目标目录条目ID
        :return: 目标目录条目
        :raises NotFoundError: 目录不存在
        :raises ValueError: 目录不属于当前项目
        """
        entry = await self.file_service.get_file_entry(folder_id)
        if not entry or not entry.is_active or not entry.is_directory:
            raise NotFoundError(f"目录不存在: {folder_id}")
        if entry.id != root_entry.id and not entry.logical_path.startswith(
            root_entry.logical_path.rstrip("/") + "/"
        ):
            raise ValueError("目标目录不属于当前项目")
        return entry

    async def upload_document(
        self,
        project_id: str,
        file,
        current_user_id: str,
        description: str | None = None,
        pid: str | None = None,
    ) -> ProjectDocument:
        """
        上传文档到项目(条目级口径): 经统一文件服务在虚拟目录 /知识库/<项目名>/[子目录]下
        创建文件条目, project_document 记录知识库口径元数据并关联 entry_id
        :param project_id: 项目ID
        :param file: 上传的文件对象
        :param current_user_id: 当前登录用户ID
        :param description: 文档描述
        :param pid: 可选父目录ID(为空上传到项目根文件夹, 须属于项目子树)
        :return: 创建的文档记录
        """
        # 校验项目存在与文件类型
        await self.validate_upload(project_id, file.filename or "")
        # 确保项目根文件夹并解析目标父目录(防越权到项目子树之外)
        root_id = await self._ensure_project_folder(project_id, current_user_id)
        target_pid = pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)

        # 统一文件服务建条目(内容哈希去重 + 引用计数由条目维护)
        entry = await self.file_service.upload_file(
            file, description, target_pid, owner_user_id=current_user_id
        )
        return await self._register_document_from_entry(
            project_id=project_id,
            entry=entry,
            description=description,
            uploaded_by=current_user_id,
        )

    async def init_multipart_upload(
        self,
        project_id: str,
        req: MultipartInitRequest,
        owner_user_id: str | None = None,
    ) -> MultipartInitResponse:
        """
        初始化分片上传(大文件/直传口径): 校验后委托统一文件服务签发凭证
        凭证签发阶段强制绑定项目根文件夹/指定子目录(忽略前端传入的 pid)
        :param project_id: 项目ID
        :param req: 初始化请求(文件名/大小/SHA-256)
        :param owner_user_id: 当前登录用户ID(目标目录归属校验用)
        :return: 会话凭证与上传模式(is_existing=True 时直接走秒传登记)
        """
        await self.validate_upload(project_id, req.filename)
        root_id = await self._ensure_project_folder(project_id, owner_user_id)
        target_pid = req.pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)
        req.pid = target_pid
        return await self.file_service.init_multipart_upload(
            req, owner_user_id=owner_user_id
        )

    async def complete_multipart_upload(
        self,
        project_id: str,
        upload_id: str,
        req: MultipartCompleteRequest,
        current_user_id: str,
    ) -> ProjectDocument:
        """
        完成分片上传: 统一文件服务对账合并并在虚拟目录中建条目 → 按知识库口径登记
        :param project_id: 项目ID
        :param upload_id: 分片会话凭证
        :param req: 完成请求(文件名/分片清单/描述/父目录)
        :param current_user_id: 当前登录用户ID
        :return: 创建的文档记录
        """
        await self.validate_upload(project_id, req.filename)
        root_id = await self._ensure_project_folder(project_id, current_user_id)
        target_pid = req.pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)
        req.pid = target_pid
        entry = await self.file_service.complete_multipart_upload(
            upload_id, req, owner_user_id=current_user_id
        )
        return await self._register_document_from_entry(
            project_id=project_id,
            entry=entry,
            description=req.description,
            uploaded_by=current_user_id,
        )

    async def create_document_from_content(
        self,
        project_id: str,
        req: EntryCreateRequest,
        current_user_id: str,
    ) -> ProjectDocument:
        """
        秒传登记(内容已存在时经统一文件服务在虚拟目录中建条目并登记知识库记录)
        :param project_id: 项目ID
        :param req: 条目创建请求(文件名/内容SHA-256/大小/父目录)
        :param current_user_id: 当前登录用户ID
        :return: 创建的文档记录
        :raises ValueError: 内容不存在或未完成上传
        """
        await self.validate_upload(project_id, req.name)
        root_id = await self._ensure_project_folder(project_id, current_user_id)
        target_pid = req.pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)
        req.pid = target_pid
        entry = await self.file_service.create_entry(req, owner_user_id=current_user_id)
        return await self._register_document_from_entry(
            project_id=project_id,
            entry=entry,
            description=req.description,
            uploaded_by=current_user_id,
        )

    ######################################知识库文件夹管理(虚拟目录条目级)######################################
    async def create_folder(
        self,
        project_id: str,
        name: str,
        current_user_id: str,
        pid: str | None = None,
    ) -> FileEntry:
        """
        在项目内创建子文件夹(虚拟目录 /知识库/<项目名>/... 下)
        :param project_id: 项目ID
        :param name: 文件夹名称
        :param current_user_id: 当前登录用户ID(条目归属者)
        :param pid: 可选父目录ID(为空创建到项目根文件夹, 须属于项目子树)
        :return: 新创建的文件夹条目
        """
        root_id = await self._ensure_project_folder(project_id, current_user_id)
        target_pid = pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)
        return await self.file_service.create_folder(
            name, target_pid, current_user_id
        )

    async def list_entries(
        self,
        project_id: str,
        pagination: PaginationParams,
        pid: str | None = None,
        name: str | None = None,
    ) -> PaginationResponse:
        """
        分页浏览项目内文件夹与文件(目录排前,名称排序; 条目级新口径)
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param pid: 可选父目录ID(为空浏览项目根文件夹, 须属于项目子树)
        :param name: 名称模糊过滤(为空不过滤)
        :return: 分页条目列表(FileEntry)
        """
        root_id = await self._ensure_project_folder(project_id)
        target_pid = pid or root_id
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, target_pid)
        response = await self.file_service.list_by_pid(target_pid, pagination, name)
        # 联查文档口径信息: 文件条目补充 document_id/解析状态(目录条目无文档记录)
        file_ids = [
            item.id for item in response.items if not item.is_directory
        ]
        doc_map: dict[str, ProjectDocument] = {}
        if file_ids:
            docs = await self.document_dao.list_by_entry_ids(file_ids)
            doc_map = {d.entry_id: d for d in docs if d.entry_id}
        enriched: list[dict] = []
        for item in response.items:
            data = item.model_dump()
            doc = doc_map.get(item.id)
            if doc:
                data.update(
                    {
                        "document_id": doc.id,
                        "parse_status": doc.parse_status,
                        "chunk_count": doc.chunk_count,
                        "error_message": doc.error_message,
                    }
                )
            enriched.append(data)
        response.items = enriched
        return response

    async def rename_folder(
        self, project_id: str, folder_id: str, new_name: str
    ) -> FileEntry:
        """
        重命名项目内子文件夹(同步更新子树逻辑路径; 不允许改项目根文件夹名, 请改项目名)
        :param project_id: 项目ID
        :param folder_id: 文件夹条目ID
        :param new_name: 新名称
        :return: 更新后的文件夹条目
        """
        root_id = await self._ensure_project_folder(project_id)
        if folder_id == root_id:
            raise ValueError("项目根文件夹名称请通过修改项目名称变更")
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, folder_id)
        return await self.file_service.rename(folder_id, new_name)

    async def delete_folder(self, project_id: str, folder_id: str) -> None:
        """
        删除项目内子文件夹(递归删除条目并释放内容引用; 不允许删项目根文件夹)
        :param project_id: 项目ID
        :param folder_id: 文件夹条目ID
        """
        root_id = await self._ensure_project_folder(project_id)
        if folder_id == root_id:
            raise ValueError("不能删除项目根文件夹")
        root_entry = await self.file_service.get_file_entry(root_id)
        await self._validate_folder_in_project(root_entry, folder_id)
        await self.file_service.delete_folder(folder_id)

    async def get_document(self, document_id: str) -> ProjectDocument | None:
        """
        获取文档详情
        :param document_id: 文档ID
        :return: 文档对象
        """
        return await self.document_dao.get(document_id)

    async def get_file_for_download(self, document_id: str) -> tuple[str, str | None, str | Path, bool]:
        """
        获取文件下载所需信息(三口径兼容: 条目级/内容级/本地旧数据)
        :param document_id: 文档ID
        :return: (原始文件名, MIME类型, 物理存储键或本地绝对路径, 是否统一存储口径)
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise NotFoundError(f"文档 {document_id} 不存在")

        if document.entry_id:
            # 条目级新口径: 联查虚拟目录条目与内容记录(物理键位于内容表)
            file_name, mime_type, file_key = (
                await self.file_service.get_file_info_for_download(document.entry_id)
            )
            return file_name, mime_type, file_key, True

        if document.content_hash:
            # 内容级旧口径: 统一存储(物理键相对存储根, 支持 local/S3)
            content = await self.file_service.get_content(document.content_hash)
            if not content or not content.physical_storage:
                logger.error(f"物理内容记录不存在: {document.content_hash}")
                raise NotFoundError(f"物理内容记录不存在: {document.content_hash}")
            return document.name, document.mime_type, content.physical_storage, True

        # 旧口径: 本地磁盘 DIR_UPLOAD/{physical_path}
        file_path = DIR_UPLOAD / document.physical_path
        if not file_path.exists():
            logger.error(f"物理文件 {file_path} 不存在")
            raise NotFoundError(f"物理文件 {file_path} 不存在")

        return document.name, document.mime_type, file_path, False

    async def list_by_project(
        self,
        project_id: str,
        pagination: PaginationParams,
        name: str | None = None,
        parse_status: str | None = None,
    ) -> PaginationResponse:
        """
        分页查询项目文档列表(支持多字段过滤)
        :param project_id: 项目ID
        :param pagination: 分页参数
        :param name: 文档名称模糊匹配
        :param parse_status: 解析状态精确过滤(pending/parsing/completed/failed)
        :return: 分页文档列表
        """
        items = await self.document_dao.list_by_project(
            project_id, pagination, name=name, parse_status=parse_status
        )
        total = await self.document_dao.count_by_project(
            project_id, name=name, parse_status=parse_status
        )
        return PaginationResponse.create(items, total, pagination)

    async def update(
        self, document_id: str, document: ProjectDocumentUpdate
    ):
        """
        更新文档元数据(仅 name/description; 条目级文档同步更新虚拟目录条目)
        :param document_id: 文档ID
        :param document: 更新数据
        """
        doc = await self.document_dao.get(document_id)
        if not doc:
            raise NotFoundError(f"文档 {document_id} 不存在")
        # 条目级: 名称/描述同步虚拟目录条目(重命名冲突直接抛错, 保持两边一致)
        if doc.entry_id and (document.name or document.description is not None):
            await self.file_service.update(
                doc.entry_id,
                FileEntryUpdate(name=document.name, description=document.description),
            )
        await self.document_dao.update(document_id, document)

    async def delete_document(self, document_id: str):
        """
        删除文档: 释放物理内容(条目级/内容级引用计数/旧口径本地文件)与数据库记录
        :param document_id: 文档ID
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise NotFoundError(f"文档 {document_id} 不存在")

        if document.entry_id:
            # 条目级新口径: 删除虚拟目录条目(内容引用-1, 归零自动清理物理文件)
            try:
                await self.file_service.delete_file(document.entry_id)
            except (ValueError, NotFoundError) as e:
                # 条目已被删除(如项目级联清理)时容忍, 继续删文档记录
                logger.warning(f"删除文件条目失败 {document.entry_id}: {e}")
        elif document.content_hash:
            # 新口径: 释放统一存储内容引用(计数归零时自动清理物理文件与内容记录)
            try:
                await self.file_service.release_content(document.content_hash)
            except Exception as e:
                logger.warning(f"释放内容引用失败 {document.content_hash}: {e}")
        else:
            # 旧口径: 直接删除本地物理文件(容忍文件已不存在的情形)
            file_path = DIR_UPLOAD / document.physical_path
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                logger.warning(f"删除物理文件失败 {file_path}: {e}")

        # 删除数据库记录
        await self.document_dao.delete(document_id)

        # 删除向量库内容
        await self.project_document_chunk_service.vector_delete_by_document_id(document_id)

    async def parse_document(
        self,
        document_id: str,
        user_id: str,
        progress_callback: IngestProgressCallback | None = None,
    ) -> bool:
        """
        解析文档(核心功能):读取文件内容,使用当前用户绑定的向量化模型和chat模型进行解析
        :param document_id: 文档ID
        :param user_id: 当前用户ID(用于获取其绑定的模型)
        :param progress_callback: 入库进度回调 async (总进度0~100, 阶段描述);
            任务队列桥接双写用, 直跑(reparse)时为 None
        :return: 是否成功
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise NotFoundError(f"文档 {document_id} 不存在")

        # 模型预检(任务队列/直跑共用): 对话+向量化模型缺失时快速失败并记录明确原因
        missing_labels = await self.ensure_parse_models(user_id)
        if missing_labels:
            raise ValueError(
                f"未配置可用的{'、'.join(missing_labels)}模型, 无法解析文档; "
                "请先在模型管理中绑定或由管理员配置默认公共模型"
            )

        # 三口径定位本地可读文件: 条目级/内容级从统一存储流式落临时文件, 旧口径读 DIR_UPLOAD
        content_hash = document.content_hash
        if not content_hash and document.entry_id:
            # 条目级兜底: 从虚拟目录条目解析内容哈希(登记时已冗余, 此处防御缺失)
            entry = await self.file_service.get_file_entry(document.entry_id)
            content_hash = entry.content_hash if entry and entry.is_active else None
        temp_input_dir: Path | None = None
        temp_output_dir: Path | None = None
        if content_hash:
            content = await self.file_service.get_content(content_hash)
            if not content or not content.physical_storage:
                logger.error(f"物理内容记录不存在: {content_hash}")
                raise NotFoundError(f"物理内容记录不存在: {content_hash}")
            temp_input_dir = Path(tempfile.mkdtemp(prefix="rag_parse_src_"))
            file_path = temp_input_dir / f"source.{document.file_extension or 'bin'}"
            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in self.file_service.stream_file_content(
                    content.physical_storage, _CHUNK_SIZE
                ):
                    await f.write(chunk)
        else:
            file_path = DIR_UPLOAD / document.physical_path
            if not file_path.exists():
                logger.error(f"物理文件 {file_path} 不存在")
                raise NotFoundError(f"物理文件 {file_path} 不存在")

        # 获取当前用户绑定的向量化模型实例 # TODO改成 文件处理专用   ocr模型单独设置
        ocr_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False)
        chat_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False,ModelType.CHAT)
        embedding_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False,ModelType.EMBEDDINGS)

        # 步骤进度快照(流水线推进时整体回写 document.parse_steps)
        steps_snapshot: dict = {}
        # 当前执行中的步骤(失败时用于定位标记)
        current_step: IngestStep = IngestStep.PARSE

        async def _report(
            step: IngestStep,
            state: IngestStepState,
            progress: float,
            message: str,
            error: str | None = None,
        ) -> None:
            """推进流水线步骤: 回写 parse_steps → 计算总进度 → 触发进度回调"""
            nonlocal current_step
            current_step = step
            steps_snapshot[step.value] = {
                "status": state.value,
                "progress": float(progress),
                "message": message,
                "error": error,
            }
            await self._write_ingest_steps(document_id, steps_snapshot)
            if progress_callback is not None:
                overall = compute_ingest_progress(steps_snapshot)
                await progress_callback(overall, message)

        # 标记解析中(供前端轮询展示解析进度)
        await self._update_parse_status(document_id, ParseStatus.PARSING)
        await _report(IngestStep.PARSE, IngestStepState.RUNNING, 5, "开始解析文档")
        try:
            temp_output_dir = Path(tempfile.mkdtemp(prefix="doc_reparse_"))
            # 1.文件解析
            chunked:list[Chunk] =await self.document_parse_service.file2chunk(file_path,ocr_llm)
            await _report(
                IngestStep.PARSE, IngestStepState.COMPLETED, 100,
                f"解析完成, 提取 {len(chunked)} 个原始块",
            )
            # 2.策略判断
            # 从解析结果中提取真实的文本样本，用于策略识别
            await _report(IngestStep.CHUNK, IngestStepState.RUNNING, 10, "分块策略识别中")
            sample_text = "\n".join([block.content for block in chunked[:10] if block.content])
            chunk_strategy_recommendation:ChunkStrategyRecommendation =await self.document_chunk_service.detect_strategy(document.name,sample_text,chat_llm)
            strategy:ChunkStrategyEnum = chunk_strategy_recommendation.strategy
            # 3.根据策略重分块
            chunk_config = ChunkConfig(
                chunk_token_num=1024,
                overlapped_percent=10,
                delimiter="\n",
                context_token_num=50,
            )
            chunked_items: list[ChunkedItem] = self.document_chunk_service.chunk(
                chunks=chunked,
                strategy=strategy,
                config=chunk_config,
                engine="ragflow",
            )

            if not chunked_items:
                logger.warning(f"文件 {file_path} 分块为空")
                await _report(IngestStep.CHUNK, IngestStepState.COMPLETED, 100, "未切分出内容块")
                await _report(IngestStep.EMBED, IngestStepState.SKIPPED, 0, "无内容块, 跳过向量化")
                await self._update_parse_status(document_id, ParseStatus.COMPLETED, chunk_count=0)
                return True

            await _report(
                IngestStep.CHUNK, IngestStepState.COMPLETED, 100,
                f"分块完成(策略: {strategy.value}), 共 {len(chunked_items)} 块",
            )

            # 4.批量向量化 (考虑队列中的并发处理, 可自行添加分批逻辑)
            await _report(IngestStep.EMBED, IngestStepState.RUNNING, 10, f"向量化 {len(chunked_items)} 个内容块")
            texts = [item.content[:8192] for item in chunked_items]
            embeddings = await embedding_llm.aembed_documents(texts)

            # 5.存入向量库 TODO 改成注册
            if not await db_vector.is_connected():
                await db_vector.connect()
            await db_vector.create_table(ProjectDocumentChunk, {"embedding": 1024})

            # 在插入新数据前，删除该文档的旧向量
            await self.project_document_chunk_service.vector_delete_by_document_id(document_id)

            # 构建插入数据
            insert_data = []
            for idx, (item, emb) in enumerate(zip(chunked_items, embeddings)):
                insert_data.append(
                    ProjectDocumentChunk(
                        sort=idx,
                        document_id=document_id,
                        project_id=document.project_id,
                        content=item.content[:8192],
                        embedding=emb,
                        sparse=None,
                        source=item.source,
                        content_types=item.content_types,
                        position=item.position,
                        metadata=item.metadata,
                    )
                )

            # 6.批量插入数据 (DBVectorMilvus.add 会自动识别 Model 类名作为 collection_name)
            await db_vector.add(insert_data)

            await _report(
                IngestStep.EMBED, IngestStepState.COMPLETED, 100,
                f"已写入 {len(insert_data)} 条向量(维度 {len(embeddings[0]) if embeddings else 0})",
            )
            # 标记解析完成并记录分块数
            await self._update_parse_status(
                document_id, ParseStatus.COMPLETED, chunk_count=len(insert_data)
            )
            logger.info(
                f"文档解析完成 document_id={document_id}, "
                f"总块数={len(insert_data)}, 向量维度={len(embeddings[0]) if embeddings else 0}"
            )
            return True

        except Exception as e:
            # 失败步骤标记(解析任务的整体状态由下方 _update_parse_status 统一置 failed)
            logger.error(f"重新解析文档失败 document_id={document_id}: {e}", exc_info=True)
            try:
                await _report(
                    current_step, IngestStepState.FAILED,
                    steps_snapshot.get(current_step.value, {}).get("progress", 0),
                    "文档入库失败", error=str(e)[:500],
                )
            except Exception as report_exc:
                logger.warning(f"回写失败步骤状态异常 document_id={document_id}: {report_exc}")
            if isinstance(e, HTTPException):
                raise
            # 标记解析失败并记录原因(截断至字段上限)
            await self._update_parse_status(
                document_id, ParseStatus.FAILED, error_message=str(e)[:1000]
            )
            raise HTTPException(status_code=500, detail=f"重新解析失败: {e}")
        finally:
            # 清理临时文件(解析输出目录 + 新口径落盘的源文件目录)
            if temp_input_dir and temp_input_dir.exists():
                shutil.rmtree(temp_input_dir, ignore_errors=True)
            if temp_output_dir and temp_output_dir.exists():
                shutil.rmtree(temp_output_dir, ignore_errors=True)

    async def _write_ingest_steps(self, document_id: str, steps: dict) -> None:
        """回写文档入库步骤进度 JSONB(失败仅告警, 不阻断解析主流程)"""
        try:
            await self.document_dao.update(
                document_id, ProjectDocumentUpdate(parse_steps=dict(steps))
            )
        except Exception as e:
            logger.warning(f"回写入库步骤进度失败 document_id={document_id}: {e}")

    def build_ingest_progress(self, document: ProjectDocument):
        """构建文档入库步骤与进度响应(流水线注册表 + 文档已存储状态合并)"""
        from module_rag.do.project_document import (
            DocumentIngestProgress,
            merge_ingest_steps,
        )

        return DocumentIngestProgress(
            document_id=document.id,
            parse_status=document.parse_status,
            progress=compute_ingest_progress(document.parse_steps),
            steps=merge_ingest_steps(document.parse_steps),
        )

    async def _update_parse_status(
        self,
        document_id: str,
        status: ParseStatus,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        """更新文档解析状态(状态跟踪供前端展示解析进度)

        :param document_id: 文档ID
        :param status: 目标状态(pending/parsing/completed/failed)
        :param chunk_count: 解析生成的分块数(仅完成时写入)
        :param error_message: 失败原因(仅失败时写入)
        """
        try:
            update_data: dict = {"parse_status": status.value if isinstance(status, ParseStatus) else str(status)}
            if chunk_count is not None:
                update_data["chunk_count"] = chunk_count
            if error_message is not None:
                update_data["error_message"] = error_message
            else:
                # 进入新状态时清除历史失败原因
                update_data["error_message"] = None
            await self.document_dao.update(
                document_id, ProjectDocumentUpdate(**update_data)
            )
        except Exception as e:
            # 状态更新失败不影响主流程
            logger.warning(f"更新解析状态失败 document_id={document_id}: {e}")