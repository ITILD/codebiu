from common.config.db import db_vector
from module_rag.do.project_document_chunk import (
    ProjectDocumentChunk,
    ProjectDocumentChunkSearchBase,
    ProjectDocumentChunkSearchResponse,
)
from pymilvus import AnnSearchRequest, RRFRanker  # 引入混合检索类
import logging

logger = logging.getLogger(__name__)


class ProjectDocumentChunkDao:
    """项目文档数据访问对象"""

    def __init__(self):
        self.collection_name = ProjectDocumentChunk.__name__.lower()

    async def search(
        self,
        query_text: str,  # 【新增】原始查询文本，用于 BM25 检索
        query_vector: list[float],  # 稠密向量，用于语义检索
        project_ids: list[str],
        limit: int = 2,
    ) -> list[ProjectDocumentChunkSearchResponse]:
        """
        执行稠密向量 + 稀疏向量(BM25) 的混合检索
        """
        if not await db_vector.async_vector.has_collection(self.collection_name):
            logger.warning(f"集合 {self.collection_name} 不存在")
            return []

        # 1. 构建稠密向量检索请求 (语义)
        # nprobe 搜索时探测的聚类中心数量（IVF 索引相关）。默认值为 10，根据需要调整。nprobe 越大，检索结果越准确，但耗时越长。
        dense_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=limit,
            expr=f"project_id in {project_ids}",
        )

        # 2. 构建全文检索的稀疏向量检索请求 (关键词 BM25)
        # 【注意】：data 直接传入原始文本字符串列表！Milvus 会自动调用 BM25 Function 处理它。
        sparse_req = AnnSearchRequest(
            data=[query_text],
            anns_field="sparse",  # 指向我们定义的 SPARSE_FLOAT_VECTOR 字段名
            param={"metric_type": "BM25"},  # BM25 默认使用内积 (IP)
            limit=limit,
            expr=f"project_id in {project_ids}",
        )

        # 3. 执行混合检索，使用 RRFRanker (倒数排名融合) 进行重排
        results: list[list[dict]] = await db_vector.async_vector.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(),  # 也可以使用 WeightedRanker(0.7, 0.3) 自定义权重
            limit=limit,
            output_fields=list(ProjectDocumentChunkSearchBase.model_fields.keys()),
        )

        # 4. 解析结果
        project_documents_chunk_search_responses: list[
            ProjectDocumentChunkSearchResponse
        ] = []
        for hits in results:
            for hit in hits:
                # 获取 Reranker 计算后的综合得分 (优先 distance，其次 score)
                score: float = hit.score
                hit_data = hit.get("entity", {})
                data = {**hit_data, "score": score}
                project_documents_chunk_search_responses.append(
                    ProjectDocumentChunkSearchResponse(**data)
                )

        return project_documents_chunk_search_responses

    async def vector_delete_by_document_id(self, document_id: str):
        # 因为 DBVectorMilvus 没封装 delete 方法，我们直接调用底层 pymilvus 客户端的 delete
        await db_vector.async_vector.delete(
            collection_name=self.collection_name,
            filter=f'document_id == "{document_id}"',
        )

    async def vector_delete_by_project_id(self, project_id: str):
        await db_vector.async_vector.delete(
            collection_name=self.collection_name, filter=f'project_id == "{project_id}"'
        )
