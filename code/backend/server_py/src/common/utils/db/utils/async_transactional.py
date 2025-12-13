# transactional.py
from functools import wraps
from sqlalchemy.ext.asyncio import AsyncSession
import logging


class AsyncTransactional:
    """
    增强版异步事务装饰器类，支持多DAO操作原子提交
    """

    def __init__(
        self,
        session_factory,
        # auto_commit: bool = True,
        # auto_rollback: bool = True,
        # nested_transaction: bool = True,  # 默认关闭更安全
        logger=None,
    ):
        self.session_factory = session_factory
        # self.auto_commit = auto_commit
        # self.auto_rollback = auto_rollback
        # self.nested_transaction = nested_transaction
        self.logger = logger or logging.getLogger(__name__)

    def transaction(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从args最后一个检查是否已有session传入
            session: AsyncSession | None = self._detect_session_in_args(
                func, args, kwargs
            )

            if session:  # 使用外部事务
                return await func(*args, **kwargs)

            # 新建事务
            async with self.session_factory() as new_session:
                try:
                    async with new_session.begin():
                        result = await func(*args, **kwargs, session=new_session)
                        return result
                except Exception as e:
                    self.logger.error(f"事务回滚: {e}", exc_info=True)
                    raise  # 抛出异常，让上层处理

        return wrapper

    def _detect_session_in_args(self, func, args, kwargs) -> AsyncSession:
        """智能检测args中的session参数"""
        # 情况1：已通过kwargs明确传递
        if "session" in kwargs:
            if any(isinstance(arg, AsyncSession) for arg in args):
                raise TypeError(
                    f"方法 `{func.__name__}` 禁止同时通过位置参数和关键字参数传递session！\n"
                    "正确用法：\n"
                    "  自动事务模式 -> `method(arg)`\n"
                    "  共享事务模式 -> `method(arg, session=your_session)`"
                )
            return kwargs["session"]

        # 情况2：从args中检测(从后向前扫描)
        for arg in reversed(args):
            if isinstance(arg, AsyncSession):
                return arg

        return None
