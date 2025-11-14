from collections.abc import AsyncGenerator
from sqlmodel.ext.asyncio.session import AsyncSession
from config.db import db_rel
# Depends 模式在架构上性能更优，数据库应用中一个至关重要的概念：工作单元 (Unit of Work)。
# 在该请求的生命周期内，所有数据库读写操作都重用这同一个事务。
# 请求成功结束时，提交整个事务。
# 如果中途任何地方发生错误，回滚整个事务。
async def get_session_rel() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖项，提供一个数据库会话并管理其生命周期。
    
    这是性能和安全性的最佳实践：
    1. `async with db_rel.session_factory() as session:`
       - 从连接池获取一个 session。
       - 使用 `async with` 确保无论发生什么，`session.close()` 最终都会被调用，
         将连接释放回连接池。
    2. `async with session.begin():`
       - 开启一个事务。
       - 同样使用 `async with`，它会在代码块成功执行后自动 `commit`，
         发生异常时自动 `rollback`。
    3. `yield session:`
       - 将处于活跃事务中的 session 对象注入到你的 API 路径操作函数中。
    """
    async with db_rel.session_factory() as session:
        async with session.begin():
            yield session