from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, delete, update, text
from sqlmodel.ext.asyncio.session import AsyncSession
from common.utils.db.do.db_config import PostgresConfig
from common.utils.db.session.interface.db_relational_interface import DBRelationInterface

class DBPostgre(DBRelationInterface):
    """
    PostgreSQL关系型数据库实现
    封装关系型数据库操作
    """

    session_factory: sessionmaker = None
    engine: create_async_engine = None
    url: str | None = None

    def __init__(self, postgres_config: PostgresConfig):
        type = "postgresql+asyncpg"
        # postgresql+asyncpg://hero:heroPass123@0.0.0.0:5432/heroes_db
        self.url = f"{type}://{postgres_config.user}:{postgres_config.password}@{postgres_config.host}:{postgres_config.port}/{postgres_config.database}"

    def connect(self, log_bool=False):
        """建立数据库连接"""
        self.engine = create_async_engine(
            self.url,
            # 开发模式下打印SQL语句
            echo=log_bool,
        )
        self.session_factory = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def is_connected(self):
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

    async def get_info(self):
        """获取数据库信息"""
        return {
            "type": "PostgreSQL",
            "url": self.url,
            "connected": await self.is_connected(),
            "tables": await self._get_table_list(),
        }

    # ############################### 会话管理 ###############################
    async def get_session(self):
        """获取异步会话"""
        session = self.session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def create_all(self):
        """创建所有表结构"""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def drop_all(self):
        """创建所有表结构"""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)

    async def exec(self, sql, session: AsyncSession = None):
        """执行原生SQL(支持外部传入session以支持事务)

        Args:
            sql: SQL语句
            session: 可选的AsyncSession对象，如果不传则自动创建新会话

        Returns:
            SELECT 返回结果列表，其他操作返回影响行数
        """
        result = await session.exec(text(sql))
        # 处理返回结果
        if sql.strip().upper().startswith("SELECT"):
            return result.fetchall()
        return result.rowcount

    async def _get_table_list(self, table_schema="public"):
        """获取所有表名 (内部方法)"""
        if not await self.is_connected():
            return []

        sql = f"""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = '{table_schema}'
        """
        tables = await self.exec(sql)
        # 去除""
        result = []
        for table in tables:
            if table[0]:
                result.append(table[0])
        return result

    async def delete(self, model, condition, session: AsyncSession):
        """基础删除方法
        return: 删除的行数
        """
        statement = delete(model).where(condition)
        result = await session.exec(statement)
        return result.rowcount

    async def delete_id(self, model, id, session: AsyncSession):
        """删除方法"""
        statement = delete(model).where(model.id == id)
        result = await session.exec(statement)
        return result.rowcount

    async def upsert(self, model, data, session: AsyncSession):
        """更新或插入数据(排除未设置的字段)
        return: 更新1或插入0
        """
        update_data = data.model_dump(exclude_unset=True)

        # 先尝试更新
        result = await session.exec(
            update(model).where(model.id == data.id).values(**update_data)
        )

        # 如果未更新则插入
        if result.rowcount == 0:
            session.add(data)
        return result.rowcount

    async def upsert_batch(self, model, data_list, session: AsyncSession):
        """
        通用的批量插入/更新方法
        适用于大多数SQL数据库(不依赖特定数据库功能)

        参数:
            model: SQLModel 表模型类
            data_list: 要插入/更新的模型实例列表
            session: 数据库会话
        """
        if not data_list:
            return 0, 0

        update_count = 0
        insert_count = 0

        for data in data_list:
            if await self.upsert(model, data, session) > 0:
                update_count += 1
            else:
                insert_count += 1

        return update_count, insert_count


if __name__ == "__main__":
    # 配置
    from config.index import conf

    db_config_dict = conf["database.postgresql"]
    db_config = PostgresConfig(**db_config_dict)

    async def main():
        db_rel = DBPostgre(db_config)
        db_rel.connect()
        list_table = await db_rel._get_table_list()
        print(list_table)

    import asyncio

    asyncio.run(main())
