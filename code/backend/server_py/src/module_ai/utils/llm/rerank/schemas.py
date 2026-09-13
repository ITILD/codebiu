from typing import Any, TypedDict


class RerankResult(TypedDict):
    node: Any                # 原始字典节点 (保留所有原始信息)
    relevance_score: float   # 归一化后 0~1 的相关性分数
    raw_score: float         # 引擎返回的原始分数(量纲由 score_min/score_max 决定)
    content: str
