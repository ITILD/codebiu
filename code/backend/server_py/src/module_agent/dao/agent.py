from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select, func, update
from common.config.db import DaoRel
from common.utils.fastapiEX.exceptions import NotFoundError
from module_agent.do.agent import Agent, AgentUpdate


class AgentDao:
    """智能体数据访问对象"""

    @DaoRel
    async def add(self, agent: Agent, session: AsyncSession | None = None) -> str:
        """新增智能体记录

        :param agent: 智能体对象
        :param session: 可选数据库会话(事务内复用)
        :return: 新建智能体的ID
        """
        session.add(agent)
        await session.flush()
        return agent.id

    @DaoRel
    async def get(self, agent_id: str, session: AsyncSession | None = None) -> Agent | None:
        """按ID查询智能体

        :param agent_id: 智能体ID
        :param session: 可选数据库会话
        :return: 智能体对象, 未找到返回None
        """
        return await session.get(Agent, agent_id)

    @DaoRel
    async def update(
        self,
        agent_id: str,
        data: AgentUpdate,
        session: AsyncSession | None = None,
    ):
        """更新指定智能体(仅更新传入字段)

        :param agent_id: 智能体ID
        :param data: 更新数据
        :param session: 可选数据库会话
        :raises: NotFoundError 智能体不存在时抛出
        """
        update_data = data.model_dump(exclude_unset=True)
        stmt = update(Agent).where(Agent.id == agent_id).values(**update_data)
        result = await session.exec(stmt)
        if result.rowcount == 0:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        await session.flush()

    @DaoRel
    async def delete(self, agent_id: str, session: AsyncSession | None = None):
        """删除指定智能体

        :param agent_id: 智能体ID
        :param session: 可选数据库会话
        :raises: NotFoundError 智能体不存在时抛出
        """
        agent = await session.get(Agent, agent_id)
        if not agent:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        await session.delete(agent)
        await session.flush()

    @DaoRel
    async def list_accessible(
        self,
        user_id: str,
        offset: int,
        limit: int,
        session: AsyncSession | None = None,
    ) -> list[Agent]:
        """查询用户可访问的智能体(公共 或 本人创建, 内置优先)

        :param user_id: 用户ID
        :param offset: 偏移量
        :param limit: 单页数量
        :param session: 可选数据库会话
        :return: 智能体列表
        """
        statement = (
            select(Agent)
            .where((Agent.is_public == True) | (Agent.created_by == user_id))  # noqa: E712
            .order_by(Agent.is_builtin.desc(), Agent.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.exec(statement)
        return result.all()

    @DaoRel
    async def count_accessible(
        self, user_id: str, session: AsyncSession | None = None
    ) -> int:
        """统计用户可访问的智能体总数

        :param user_id: 用户ID
        :param session: 可选数据库会话
        :return: 数量
        """
        statement = (
            select(func.count())
            .select_from(Agent)
            .where((Agent.is_public == True) | (Agent.created_by == user_id))  # noqa: E712
        )
        result = await session.exec(statement)
        return result.one()

    @DaoRel
    async def list_by_ids(
        self, agent_ids: list[str], session: AsyncSession | None = None
    ) -> list[Agent]:
        """按ID列表批量查询(种子幂等写入用)

        :param agent_ids: 智能体ID列表
        :param session: 可选数据库会话
        :return: 命中的智能体列表
        """
        if not agent_ids:
            return []
        statement = select(Agent).where(Agent.id.in_(agent_ids))
        result = await session.exec(statement)
        return result.all()
