from module_rag.dao.project_document_chunk import ProjectDocumentChunkDao
from module_rag.do.project_document_chunk import (
    SearchRequest,
    ProjectDocumentChunkSearchResponse,
)
from module_ai.utils.llm.do.llm_type import ModelType
from module_rag.service.user_model import UserModelService
from module_ai.service.llm_base import LLMBaseService
import logging
logger = logging.getLogger(__name__)


class ProjectDocumentChunkService:
    """项目文档数据向量服务对象"""

    def __init__(
        self,
        project_document_chunk_dao: ProjectDocumentChunkDao | None = None,
        user_model_service: UserModelService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.project_document_chunk_dao = (
            project_document_chunk_dao or ProjectDocumentChunkDao()
        )
        self.user_model_service = user_model_service or UserModelService()

    async def search(
        self, request: SearchRequest, user_id: str
    ) -> list[ProjectDocumentChunkSearchResponse]:
        """搜索文档"""
        # 获取模型实例并将查询文本转向量
        embedding_llm = await self.user_model_service.get_llm_by_user_id(
            user_id, False, ModelType.EMBEDDINGS
        )
        try:
            query_vector = await embedding_llm.aembed_query(request.query_content)
            if not query_vector:
                raise ValueError("向量化模型返回空结果")
        except Exception as e:
            raise ValueError("文本向量化失败")

        # 4. 调用 DAO 层执行 Milvus 检索
        results: list[ProjectDocumentChunkSearchResponse] = (
            await self.project_document_chunk_dao.search(
                query_text=request.query_content,
                query_vector=query_vector,
                project_ids=request.project_ids,
                limit=request.limit,
            )
        )
        logger.info(
            f"[Search] Milvus 粗排完成 | query='{request.query_content[:50]}' | "
            f"召回={len(results)} enable_rerank={request.enable_rerank} score_threshold={request.score_threshold}"
        )

        # rerank: 仅当显式开启(深度思考)时执行精排,并按 score_threshold 过滤低分结果
        if request.enable_rerank:
            rerank_llm = await self.user_model_service.get_llm_by_user_id(
                user_id, False, ModelType.RERANK
            )
            if rerank_llm:
                logger.info(f"[Search] 深度思考已开启, 启动 Rerank 精排 | 候选数={len(results)}")
                results = await self._rerank(
                    rerank_llm,
                    request.query_content,
                    results,
                    request.rerank_limit,
                    request.score_threshold,
                )
                logger.info(f"[Search] Rerank 精排完成 | 最终返回={len(results)} 条")
            else:
                logger.warning(f"[Search] 深度思考已开启但用户未绑定 Rerank 模型, 跳过精排")
        else:
            logger.info(f"[Search] 深度思考未开启, 跳过 Rerank 精排")

        return results

    async def _rerank(
        self,
        rerank_llm,
        query: str,
        candidates: list[ProjectDocumentChunkSearchResponse],
        top_n: int,
        score_threshold: float = 0.5
    ) -> list[ProjectDocumentChunkSearchResponse]:
        """
        使用 Rerank 模型对粗排结果进行精排重排序
        :param rerank_llm: Rerank 模型实例
        :param query: 用户查询文本
        :param candidates: Milvus 粗排召回的候选列表
        :param top_n: 最终返回条数
        :return: 精排后的结果列表
        """
        doc_list = []
        for res in candidates:
            text_content = getattr(res, 'content', '') or getattr(res, 'chunk_content', '') or ''
            doc_list.append({
                "content": text_content,
                "node": res
            })

        logger.info(
            f"[Rerank] 准备精排 | query='{query[:50]}' | 候选={len(candidates)} | "
            f"top_n={top_n} score_threshold={score_threshold}"
        )

        try:
            reranked_results = await rerank_llm.arerank_dict_list(
                query=query,
                doc_list=doc_list,
                sort_key="content",
                top_n=top_n,
                score_threshold=score_threshold  # 可以根据需要调整阈值
            )
            logger.info(
                f"[Rerank] 精排结束 | 精排前={len(candidates)} 精排后={len(reranked_results)} | " 
            )
            # return [item["node"] for item in reranked_results]
            final_results = []
            for item in reranked_results:
                obj = item["node"]
                
                # 顺手将 Rerank 的高精度分数，更新到原始对象的 score 字段
                if hasattr(obj, "score"):
                    obj.score = item["relevance_score"]
                final_results.append(obj)
            return final_results

        except Exception as e:
            logger.warning(f"Rerank 重排序失败，降级返回向量检索结果: {e}")
            return candidates[:top_n]

    async def vector_delete_by_document_id(self, document_id: str):
        """根据文档ID删除向量"""
        await self.project_document_chunk_dao.vector_delete_by_document_id(document_id)

    async def vector_delete_by_project_id(self, project_id: str):
        """根据项目ID删除向量"""
        await self.project_document_chunk_dao.vector_delete_by_project_id(project_id)

    # ################ 全库重向量化(系统管理员运维操作, Celery 任务与直跑接口共用) ################

    async def revectorize_all(
        self,
        model_id: str | None = None,
        progress_cb=None,
    ) -> dict:
        """
        以目标 embedding 模型重算 Milvus 中所有文档 chunk 向量
        (功能服务层实现: Celery 任务与 controller 直跑接口共用, 保证"零逻辑重复")

        实现要点:
        - 按文档逐个处理, 规避 Milvus query 的 offset+limit 16384 上限
        - 新旧模型维度一致: 直接 upsert 更新向量(保留原 chunk id)
        - 维度不一致: 全量读出元数据(不含向量) -> drop collection -> 重建表 -> 重新写入

        :param model_id: 目标向量化模型配置ID(None 时使用当前生效的默认公共 embedding 模型)
        :param progress_cb: 可选异步进度回调 (processed_docs, total_docs, chunks, model_label, dim_changed);
                            Celery 任务传入用于双写进度, 直跑接口传 None
        :return: 统计结果 {total_chunks, processed_chunks, documents, model, dim_changed}
        :raises ValueError: 模型不存在/加载失败/无生效默认模型
        """
        from module_ai.dao.model_config import ModelConfigDao
        from module_ai.service.llm_base import LLMBaseService
        from module_rag.dao.project_document import ProjectDocumentDao
        from module_rag.do.project_document_chunk import ProjectDocumentChunk
        from common.config.db import db_vector

        # 1. 确定目标 embedding 模型
        if not model_id:
            fallback = await ModelConfigDao().get_default_by_type(
                ModelType.EMBEDDINGS.value, active_only=True
            )
            if fallback is None:
                raise ValueError("没有生效的默认公共向量化模型, 请先在模型配置中设置")
            model_id = fallback.id
        model_config = await ModelConfigDao().get(model_id)
        if model_config is None:
            raise ValueError(f"模型配置不存在: {model_id}")
        embeddings_llm = await LLMBaseService().get_llm(model_id, False)
        if embeddings_llm is None:
            raise ValueError(f"加载向量化模型失败: {model_config.model}")
        model_label = model_config.display_name or model_config.model

        # 2. 探测新模型向量维度
        probe = await embeddings_llm.aembed_query("维度探测")
        if not probe:
            raise ValueError("向量化模型返回空结果, 无法探测维度")
        new_dim = len(probe)

        # 3. 检查 collection 与旧维度
        if not await db_vector.is_connected():
            await db_vector.connect()
        collection_exists = await db_vector.async_vector.has_collection(
            "projectdocumentchunk"  # 与 ProjectDocumentChunkDao 一致: 类名小写
        )
        if not collection_exists:
            logger.info("向量集合不存在, 无需重向量化")
            return {"total_chunks": 0, "processed_chunks": 0, "documents": 0,
                    "model": model_label, "dim_changed": False}
        old_dim: int | None = None
        try:
            schema = await db_vector.async_vector.describe_collection("projectdocumentchunk")
            for field in schema.fields:
                if field.name == "embedding":
                    old_dim = int(field.params.get("dim", 0))
        except Exception as e:
            logger.warning(f"读取 collection 维度失败, 视为维度一致处理: {e}")
        dim_changed = old_dim is not None and old_dim != new_dim

        # 4. 遍历文档处理
        document_ids = await ProjectDocumentDao().list_all_ids()
        total_documents = len(document_ids)
        processed_chunks = 0
        # 维度不一致时: 先全部读出元数据(不含向量)暂存, 再重建 collection 写回
        pending_rows: list[dict] = []
        if dim_changed:
            logger.info(f"向量维度变更 {old_dim} -> {new_dim}, 将重建 collection 后全量写入")

        for idx, doc_id in enumerate(document_ids):
            rows = await db_vector.async_vector.query(
                collection_name="projectdocumentchunk",
                filter=f'document_id == "{doc_id}"',
                output_fields=[
                    f for f in ProjectDocumentChunk.model_fields.keys()
                    if f not in ("embedding", "sparse")
                ],
                limit=16384,
            )
            if rows:
                texts = [r.get("content") or "" for r in rows]
                vectors = await embeddings_llm.aembed_documents(texts)
                if dim_changed:
                    # 暂存新向量, 稍后随重建的 collection 一起写入
                    for row, vec in zip(rows, vectors):
                        row["embedding"] = vec
                    pending_rows.extend(rows)
                else:
                    # 维度一致: upsert 原地更新向量(保留原 id)
                    upsert_data = []
                    for row, vec in zip(rows, vectors):
                        upsert_data.append({**row, "embedding": vec, "sparse": None})
                    await db_vector.async_vector.upsert("projectdocumentchunk", upsert_data)
                processed_chunks += len(rows)
            # 进度回调(任务侧双写 task_queue 表与结果后端; 直跑为 None)
            if progress_cb is not None:
                try:
                    await progress_cb(idx + 1, total_documents, processed_chunks,
                                      model_label, dim_changed)
                except Exception as e:
                    logger.debug(f"重向量化进度回调失败(忽略): {e}")

        # 5. 维度不一致: 重建 collection 并写入全部新向量
        if dim_changed:
            await db_vector.async_vector.drop_collection("projectdocumentchunk")
            await db_vector.create_table(ProjectDocumentChunk, {"embedding": new_dim})
            batch: list[ProjectDocumentChunk] = []
            for row in pending_rows:
                batch.append(ProjectDocumentChunk(
                    id=row.get("id"),
                    sort=row.get("sort", 0),
                    document_id=row.get("document_id"),
                    project_id=row.get("project_id"),
                    content=row.get("content") or "",
                    source=row.get("source") or "",
                    content_types=row.get("content_types") or [],
                    position=row.get("position") or {},
                    metadata=row.get("metadata"),
                    embedding=row.get("embedding"),
                    sparse=None,
                ))
                if len(batch) >= 500:
                    await db_vector.add(batch)
                    batch = []
            if batch:
                await db_vector.add(batch)
        else:
            # upsert 后 flush 保证立即可检索
            await db_vector.async_vector.flush("projectdocumentchunk")

        logger.info(
            f"全库重向量化完成 model={model_label} dim {old_dim}->{new_dim} "
            f"documents={total_documents} chunks={processed_chunks}"
        )
        return {"total_chunks": processed_chunks, "processed_chunks": processed_chunks,
                "documents": total_documents, "model": model_label, "dim_changed": dim_changed}
