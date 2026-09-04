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
