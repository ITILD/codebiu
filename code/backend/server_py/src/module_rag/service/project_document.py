import asyncio
import json
import logging
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import HTTPException, UploadFile
from langchain.chat_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings

from common.config.db import db_vector
from common.config.path import DIR_UPLOAD
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from common.utils.path.dir import Dir
from module_ai.service.llm_base import LLMBaseService
from module_ai.service.model_config import ModelConfigService
from module_ai.utils.llm.do.llm_type import ModelType
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
    ParseStatus,
    ProjectDocument,
    ProjectDocumentCreate,
    ProjectDocumentUpdate,
)
from module_rag.do.project_document_chunk import ProjectDocumentChunk
from module_rag.service.project_document_chunk import ProjectDocumentChunkService
from module_rag.service.user_model import UserModelService

logger = logging.getLogger(__name__)

# 单块读取大小(64KB)
_CHUNK_SIZE = 1024 * 64


class ProjectDocumentService:
    """项目文档服务：处理文件上传/下载/删除及元数据管理"""
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
    ):
        self.document_dao = document_dao or ProjectDocumentDao()
        self.project_dao = project_dao or ProjectDao()
        self.user_model_service = user_model_service or UserModelService()
        self.llm_base_service = llm_base_service or LLMBaseService()
        self.model_config_service = model_config_service or ModelConfigService()
        self.document_parse_service = document_parse_service or DocumentParseService()
        # 负责文档分块策略选择和分块操作
        self.document_chunk_service = document_chunk_service or DocumentChunkService()

        self.project_document_chunk_service = project_document_chunk_service or ProjectDocumentChunkService()

    async def upload_document(
        self,
        project_id: str,
        file: UploadFile,
        current_user_id: str,
        description: str | None = None,
    ) -> ProjectDocument:
        """
        上传文档到项目(保存至 DIR_UPLOAD/{project_id}/{uuid_filename})
        :param project_id: 项目ID(作为文件夹名)
        :param file: 上传的文件对象
        :param current_user_id: 当前登录用户ID
        :param description: 文档描述
        :return: 创建的文档记录
        """
        # 校验项目存在
        project = await self.project_dao.get(project_id)
        if not project:
            logger.error(f"项目 {project_id} 不存在")
            raise LookupError(f"项目 {project_id} 不存在")
        ext = Path(file.filename).suffix.lstrip(".").lower() if file.filename else ""
        # 校验文件名与扩展名
        if not file.filename:
            raise LookupError("文件名不能为空")
        if not DocType.is_allowed_extension(ext):
            raise LookupError(f"不支持的文件类型 '{ext}'，允许: {'/'.join(DocType.ALLOWED_EXTENSIONS)}")

        # 确保项目目录存在(以 project_id 作为文件夹名)
        project_dir = Dir.ensure_dir(DIR_UPLOAD / project_id)

        # 生成唯一文件名，避免冲突与编码问题
        document_id = uuid4().hex
        unique_filename = f"{document_id}.{ext}"
        save_path = project_dir / unique_filename

        # 流式写入磁盘
        file_size = 0
        try:
            async with aiofiles.open(save_path, "wb") as f:
                while True:
                    chunk = await file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    await f.write(chunk)
                    file_size += len(chunk)
        except Exception as e:
            logger.error(f"写入文件失败: {e}")
            # 清理可能写入的残留文件
            if save_path.exists():
                save_path.unlink()
            raise LookupError("文件上传失败")

        # 相对 DIR_UPLOAD 的物理路径(便于迁移)
        physical_path = f"{project_id}/{unique_filename}"

        # 构造文档记录
        document_create = ProjectDocumentCreate(
            id=document_id,
            project_id=project_id,
            name=file.filename,
            file_extension=ext,
            mime_type=file.content_type,
            file_size_bytes=file_size,
            physical_path=physical_path,
            description=description,
            uploaded_by=current_user_id,
        )
        document = await self.document_dao.add(document_create)
        return document

    async def get_document(self, document_id: str) -> ProjectDocument | None:
        """
        获取文档详情
        :param document_id: 文档ID
        :return: 文档对象
        """
        return await self.document_dao.get(document_id)

    async def get_file_for_download(self, document_id: str) -> tuple[str, str | None, Path]:
        """
        获取文件下载所需信息
        :param document_id: 文档ID
        :return: (原始文件名, MIME类型, 物理文件绝对路径)
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise LookupError(f"文档 {document_id} 不存在")

        file_path = DIR_UPLOAD / document.physical_path
        if not file_path.exists():
            logger.error(f"物理文件 {file_path} 不存在")
            raise LookupError(f"物理文件 {file_path} 不存在")

        return document.name, document.mime_type, file_path

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
        更新文档元数据(仅 name/description)
        :param document_id: 文档ID
        :param document: 更新数据
        """
        await self.document_dao.update(document_id, document)

    async def delete_document(self, document_id: str):
        """
        删除文档: 同时删除物理文件与数据库记录
        :param document_id: 文档ID
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise LookupError(f"文档 {document_id} 不存在")

        # 删除物理文件(容忍文件已不存在的情形)
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

    async def parse_document(self, document_id: str, user_id: str) -> bool:
        """
        解析文档(核心功能):读取文件内容,使用当前用户绑定的向量化模型和chat模型进行解析
        :param document_id: 文档ID
        :param user_id: 当前用户ID(用于获取其绑定的模型)
        :param preset_id: 使用大模型决定的分块策略ID
        :return: 是否成功
        """
        document = await self.document_dao.get(document_id)
        if not document:
            logger.error(f"文档 {document_id} 不存在")
            raise LookupError(f"文档 {document_id} 不存在")

        file_path = DIR_UPLOAD / document.physical_path
        if not file_path.exists():
            logger.error(f"物理文件 {file_path} 不存在")
            raise LookupError(f"物理文件 {file_path} 不存在")
        
        # 获取当前用户绑定的向量化模型实例 # TODO改成 文件处理专用   ocr模型单独设置
        ocr_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False) 
        chat_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False,ModelType.CHAT)
        embedding_llm: BaseChatModel | None = await self.user_model_service.get_llm_by_user_id(user_id,False,ModelType.EMBEDDINGS)

        temp_output_dir = None
        # 标记解析中(供前端轮询展示解析进度)
        await self._update_parse_status(document_id, ParseStatus.PARSING)
        try:
            temp_output_dir = Path(tempfile.mkdtemp(prefix="doc_reparse_"))
            # 1.文件解析
            chunked:list[Chunk] =await self.document_parse_service.file2chunk(file_path,ocr_llm)
            # 2.策略判断
            # 从解析结果中提取真实的文本样本，用于策略识别
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
                await self._update_parse_status(document_id, ParseStatus.COMPLETED, chunk_count=0)
                return True

            # 4.批量向量化 (考虑队列中的并发处理, 可自行添加分批逻辑)
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

            # 标记解析完成并记录分块数
            await self._update_parse_status(
                document_id, ParseStatus.COMPLETED, chunk_count=len(insert_data)
            )
            logger.info(
                f"文档解析完成 document_id={document_id}, "
                f"总块数={len(insert_data)}, 向量维度={len(embeddings[0]) if embeddings else 0}"
            )
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"重新解析文档失败 document_id={document_id}: {e}", exc_info=True)
            # 标记解析失败并记录原因(截断至字段上限)
            await self._update_parse_status(
                document_id, ParseStatus.FAILED, error_message=str(e)[:1000]
            )
            raise HTTPException(status_code=500, detail=f"重新解析失败: {e}")
        finally:
            # 清理临时文件
            if temp_output_dir and temp_output_dir.exists():
                shutil.rmtree(temp_output_dir, ignore_errors=True)

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