from pydantic import BaseModel
from datetime import datetime
# ################################################## 硬件信息模型
# 磁盘信息模型
class DiskInfo(BaseModel):
    total: float  # 单位：GB
    used: float   # 单位：GB
    percent: float # 百分比

# 内存信息模型
class MemoryInfo(BaseModel):
    total: float  # 单位：GB
    used: float   # 单位：GB
    percent: float # 百分比

# CPU 信息模型
class CPUInfo(BaseModel):
    percent: float         # CPU 使用率百分比
    cores: int            # 物理核心数
    threads: int          # 逻辑线程数

# GPU 信息模型
class GPUInfo(BaseModel):
    vendor: str           # GPU 厂商（NVIDIA 或 AMD）
    id: int               # GPU ID
    name: str             # GPU 名称
    total: float          # 显存总量（单位：MB）
    used: float           # 已用显存（单位：MB）
    percent: float        # 显存使用率百分比
    temp: float           # GPU 温度（单位：°C）

# 硬件状态模型
class HardwareStatus(BaseModel):
    disk: DiskInfo
    memory: MemoryInfo
    cpu: CPUInfo
    gpu: list[GPUInfo]    # 支持多个 GPU
    timestamp: datetime   # 时间戳
# ################################################## 网络状态   
class NetworkStatus(BaseModel):
    url: str # URL
    connect_success: bool
    # elapsed: float # 耗时    
# ################################################## 进程状态

# 进程信息模型
class ProcessInfo(BaseModel):
    pid: int
    name: str
    status: str
    cpu_percent: float    # CPU 使用率百分比
    memory_percent: float # 内存使用率百分比
    memory_rss: float     # RSS 内存占用（单位：MB）
    create_time: datetime # 进程创建时间
    exe: str              # 可执行文件路径
    cmdline: list[str]    # 命令行参数

# 顶部进程信息模型
class TopProcessInfo(BaseModel):
    pid: int
    user: str
    name: str
    cpu: float            # CPU 使用率百分比
    memory: float         # 内存使用率百分比
    rss_mb: float         # RSS 内存占用（单位：MB）