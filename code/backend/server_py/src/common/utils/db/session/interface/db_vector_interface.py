from abc import ABC, abstractmethod
from common.utils.db.do.db_config import DBConfig


class DBVectorInterface(ABC):
    """
    向量化数据库接口
    """

    def __init__(self, config: DBConfig) -> None:
        """
        初始化方法。

        子类必须实现此方法，通常用于接收数据库连接所需的配置参数
        (例如：主机地址、端口、用户名、密码、数据库名等)。
        """
        raise NotImplementedError("子类必须实现 __init__ 方法")
    def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        raise NotImplementedError("子类必须实现 connect 方法")
