# DBCacheInterface
from abc import ABC, abstractmethod

class DBCacheInterface(ABC):
    """
    数据库缓存接口
    定义了缓存数据库操作的基本方法
    """
    
    # __init__
    @abstractmethod
    def __init__(self):
        """
        初始化方法。

        子类必须实现此方法，通常用于接收数据库连接所需的配置参数
        （例如：主机地址、端口、用户名、密码、数据库名等）。
        """
        raise NotImplementedError("子类必须实现 __init__ 方法")

    @abstractmethod
    def connect(self, log_bool=False):
        """
        建立数据库连接。

        子类需要实现具体的数据库连接逻辑。
        """
        raise NotImplementedError("子类必须实现 connect 方法")