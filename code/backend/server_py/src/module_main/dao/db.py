from common.config.db import db_rel
import logging
logger = logging.getLogger(__name__)
class TableDao:
    """
    数据库基础操作类
    提供与数据库表相关的CRUD操作
    """
    @staticmethod
    async def create():
        """
        创建所有未创建的数据库表
        
        返回:
            None
        """
        # 关系数据库
        await db_rel.create_all()
    @staticmethod
    async def reset():
        """
        重置所有数据库表

        返回:
            None
        """
        await db_rel.drop_all()
        await db_rel.create_all()
                    

logger.info('ok...dao_index')