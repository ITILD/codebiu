# ANSI 转义序列
from enum import StrEnum


# 定义颜色的 ANSI 转义序列枚举
class Color(StrEnum):
    RESET = '\033[0m'          # 重置颜色
    RED = '\033[91m'           # 红色
    GREEN = '\033[92m'         # 绿色
    YELLOW = '\033[93m'        # 黄色
    BLUE = '\033[94m'          # 蓝色
    MAGENTA = '\033[95m'       # 品红
    CYAN = '\033[96m'          # 青色

# 定义日志级别与颜色的映射枚举
class LogLevelColor(StrEnum):
    DEBUG = Color.GREEN
    INFO = Color.CYAN
    WARNING = Color.YELLOW
    ERROR = Color.RED
    CRITICAL = Color.MAGENTA