from pydantic import BaseModel


class PlatformInfo(BaseModel):
    """平台信息模型"""

    system: str  # 操作系统名称
    machine: str  # 机器架构
    bitness: str  # 系统位数
    libc: str | None = None  # Linux系统libc版本
