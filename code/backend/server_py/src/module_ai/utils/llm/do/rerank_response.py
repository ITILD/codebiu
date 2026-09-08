from typing import TypedDict


class RerankResult(TypedDict):
    node: any                # 原始字典节点 (保留所有原始信息)
    relevance_score: float   # 重排相关性分数
    content: str