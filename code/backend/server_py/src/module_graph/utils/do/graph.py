from pydantic import BaseModel
from enum import Enum


class Node(BaseModel):
    """节点"""

    id: str = None

    def __hash__(self):
        """使Node对象可哈希"""
        return hash(self.id)


class Relation(BaseModel):
    """关系"""

    cid: str = None
    pid: str = None
    rel: str = None

    def __hash__(self):
        """使Relation对象可哈希"""
        return hash((self.cid, self.pid, self.rel))


class NodeStatus(str, Enum):
    """节点状态枚举"""

    PENDING = "pending"  # 等待处理
    READY = "ready"  # 准备就绪
    PROCESSING = "processing"  # 处理中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
