from enum import StrEnum

class TaskStatus(StrEnum):
    """
    Generic lifecycle states for asynchronous or long-running tasks.
    Suitable for uploads, downloads, data processing, batch jobs, etc.
    All states are terminal unless noted.
    """
    # --- 非终态（任务仍在进行中）---
    PENDING = "pending"         # 已创建，等待资源/调度（如排队）
    RUNNING = "running"         # 正在执行中
    PAUSED = "paused"           # 暂停（可恢复）
    
    # --- 终态（任务已结束，不可变）---
    SUCCESS = "success"     # 成功完成（无错误）
    FAILED = "failed"           # 执行失败（含异常、超时、校验失败等）
    CANCELLED = "cancelled"     # 被用户或系统主动取消
    EXPIRED = "expired"         # 因超时或过期自动终止（如预签名失效）