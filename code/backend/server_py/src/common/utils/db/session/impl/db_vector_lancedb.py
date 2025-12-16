from lancedb import connect_async, AsyncConnection
from lancedb.pydantic import LanceModel, Vector
from common.utils.db.do.db_config import LancedbConfig
from common.utils.db.session.interface.db_vector_interface import DBVectorInterface
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VectorBase(LanceModel):
    """向量基类"""
    content_vec: Vector = Vector(1024)


class DBVectorLancedb(DBVectorInterface):
    """
    LanceDB向量数据库实现
    封装向量数据库操作
    """

    database: str = None
    async_con: AsyncConnection = None

    def __init__(self, lancedb_config: LancedbConfig):
        """
        初始化LanceDB向量数据库连接

        Args:
            lancedb_config: LanceDB数据库配置对象
        """
        self.database = Path(lancedb_config.database).resolve().as_posix()

    async def connect(self, log_bool=False):
        """
        建立数据库连接

        Args:
            log_bool: 是否启用日志
        """
        try:
            # 创建LanceDB客户端实例
            self.async_con = await connect_async(self.database)

            if log_bool:
                logger.info(f"LanceDB数据库连接成功: {self.database}")
        except Exception as e:
            raise Exception(f"LanceDB数据库连接失败: {e}")
        
        async def create_all(self):
            """创建所有表结构"""
            pass

