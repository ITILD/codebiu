# 重排序服务依赖注入
from module_ai.service.rerank import RerankService

# 全局服务实例(单例)
rerank_service = RerankService()


def get_rerank_service() -> RerankService:
    """获取重排序服务实例(单例, 作为 FastAPI 依赖项)"""
    return rerank_service
