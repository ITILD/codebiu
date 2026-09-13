from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from common.config.db import DaoRel
from module_agent.do.agent_run import AgentRun


class AgentRunDao:
    """智能体运行历史数据访问对象"""

    @DaoRel
    async def add(self, run: AgentRun, session: AsyncSession | None = None) -> str:
        """新增运行历史记录

        :param run: 运行记录对象
        :param session: 可选数据库会话(事务内复用)
        :return: 运行记录ID
        """
        session.add(run)
        await session.flush()
        return run.id

    @DaoRel
    async def get_run(
        self,
        run_id: str,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> AgentRun | None:
        """按ID查询单条运行记录(仅本人)

        :param run_id: 运行记录ID
        :param user_id: 当前用户ID(非本人记录不可见)
        :param session: 可选数据库会话
        :return: 运行记录, 未找到或非本人返回None
        """
        statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        result = await session.exec(statement)
        return result.first()

    @DaoRel
    async def list_by_agent_user(
        self,
        agent_id: str,
        user_id: str,
        offset: int,
        limit: int,
        session: AsyncSession | None = None,
    ) -> list[AgentRun]:
        """分页查询某用户在指定智能体下的运行历史(按运行时间倒序)

        :param agent_id: 智能体ID
        :param user_id: 运行用户ID(仅查本人记录)
        :param offset: 偏移量
        :param limit: 单页数量
        :param session: 可选数据库会话
        :return: 运行记录列表
        """
        statement = (
            select(AgentRun)
            .where(AgentRun.agent_id == agent_id, AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_by_agent_user(
        self,
        agent_id: str,
        user_id: str,
        session: AsyncSession | None = None,
    ) -> int:
        """统计某用户在指定智能体下的运行历史总数

        :param agent_id: 智能体ID
        :param user_id: 运行用户ID
        :param session: 可选数据库会话
        :return: 记录总数
        """
        statement = (
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.agent_id == agent_id, AgentRun.user_id == user_id)
        )
        result = await session.exec(statement)
        return result.one()
