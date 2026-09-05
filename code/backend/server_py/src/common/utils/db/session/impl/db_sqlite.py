from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker, Session

# 防止注入
from sqlalchemy import text
from common.utils.db.do.db_config import SqliteConfig
from common.utils.db.session.interface.db_relational_interface import (
    DBRelationInterface,
)
import json


# Relational
class DBSqlite(DBRelationInterface):
    """SQLite 数据库基础实现类"""

    url: str | None = None
    engine = None
    session_factory = sessionmaker | None

    def __init__(self, sqliteConfig: SqliteConfig):
        """初始化 SQLite 数据库连接

        Args:
            database: 数据库文件路径，可以是字符串或 Path 对象
        """
        # 使用 pathlib 规范化路径
        try:
            self.database = Path(sqliteConfig.database).absolute()
            self.url = f"sqlite+aiosqlite:///{self.database}"
        except Exception as e:
            raise Exception(f"数据库路径错误: {e}")

    def connect(self, log_bool=False):
        """建立数据库连接"""
        self.engine = create_async_engine(
            self.url,
            echo=log_bool,  # 开发模式下打印SQL语句
            # pool_pre_ping=True,  # 禁止在异步环境中使用,该选项在异步环境下存在兼容性问题，可能导致连接关闭异常或 CancelledError。建议改用 pool_recycle 配合数据库层的 keepalive 配置。
            pool_recycle=300,  # 5 分钟后自动重建连接 比 pool_pre_ping 更适合异步场景，因为它是“主动过期”而非“被动检测”
            # 确保中文不被转义
            json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
        )
        self.session_factory = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def is_connected(self) -> bool:
        """检查连接状态"""
        return bool(self.engine and not await self.engine.dispose())

    async def reconnect(self):
        """重新连接数据库"""
        await self.disconnect()
        self.connect()

    async def disconnect(self):
        """断开数据库连接"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    async def get_info(self) -> dict:
        """获取数据库信息"""
        return {
            "type": "SQLite",
            "url": self.url,
            "connected": await self.is_connected(),
            "tables": await self._get_table_list(),
        }

    async def get_session(self):
        """获取异步会话"""
        session: AsyncSession
        async with self.session_factory() as session:
            yield session

    async def create_all(self):
        """创建所有表结构"""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def drop_all(self):
        """创建所有表结构"""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    async def execute(self, sql: str):
        """执行原生SQL

        Args:
            sql: SQL语句 (支持 :param 参数)
            params: 参数字典

        Returns:
            SELECT 返回结果列表，其他操作返回影响行数
        """
        session: AsyncSession
        async with self.session_factory() as session:
            result = await session.exec(text(sql))
            await session.commit()

        # 处理不同SQL类型的返回结果
        if sql.strip().upper().startswith("SELECT"):
            return result.fetchall()
        else:
            return result.rowcount

    async def _get_table_list(self) -> list[str]:
        """获取所有表名 (内部方法)"""
        if not await self.is_connected():
            return []

        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        tables = await self.execute(sql)
        # 去除""
        result = []
        for table in tables:
            if table[0]:
                result.append(table[0])
        return result
