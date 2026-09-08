from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from common.utils.fastapiEX.exceptions import NotFoundError, BusinessError
from module_authorization.config.casbin_rule import auth_manager
from module_agent.config.agent_seed import BUILTIN_AGENTS
from module_agent.dao.agent import AgentDao
from module_agent.do.agent import Agent, AgentCreate, AgentUpdate

import logging

logger = logging.getLogger(__name__)


def _is_admin(user_id: str) -> bool:
    """判断是否全局管理员(admin 角色穿透一切权限)"""
    enforcer = auth_manager.enforcer
    return bool(enforcer is not None and enforcer.has_grouping_policy(user_id, "admin", "*"))


class AgentService:
    """智能体管理服务(CRUD + 内置种子 + 归属校验)"""

    def __init__(self, agent_dao: AgentDao | None = None):
        """依赖注入构造器:初始化所需的数据访问对象"""
        self.agent_dao = agent_dao or AgentDao()

    async def seed_builtin_agents(self) -> None:
        """内置公共智能体幂等写入(启动时调用; 已存在则跳过, 不覆盖用户可能的修改)"""
        try:
            existing_ids = {a.id for a in await self.agent_dao.list_by_ids(
                [item["id"] for item in BUILTIN_AGENTS]
            )}
            for item in BUILTIN_AGENTS:
                if item["id"] in existing_ids:
                    continue
                agent = Agent(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    system_prompt=item["system_prompt"],
                    is_public=True,
                    is_builtin=True,
                    created_by=None,
                )
                await self.agent_dao.add(agent)
                logger.info(f"内置智能体已写入: {item['name']}({item['id']})")
        except Exception as e:
            # 种子失败不阻断启动(如下次重启重试), 仅记录错误
            logger.error(f"内置智能体种子写入失败: {e}", exc_info=True)

    async def list_accessible(self, user_id: str, pagination: PaginationParams) -> PaginationResponse:
        """分页获取用户可访问的智能体(公共 或 本人创建)"""
        items = await self.agent_dao.list_accessible(
            user_id, pagination.offset, pagination.limit
        )
        total = await self.agent_dao.count_accessible(user_id)
        return PaginationResponse.create(items, total, pagination)

    async def get(self, agent_id: str) -> Agent | None:
        """按ID查询智能体"""
        return await self.agent_dao.get(agent_id)

    async def create(self, user_id: str, data: AgentCreate) -> str:
        """创建自定义简单智能体(私有, 仅创建者可用)"""
        agent = Agent(
            name=data.name.strip(),
            description=data.description.strip(),
            system_prompt=data.system_prompt.strip(),
            is_public=False,
            is_builtin=False,
            created_by=user_id,
        )
        return await self.agent_dao.add(agent)

    async def update(self, agent_id: str, user_id: str, data: AgentUpdate) -> None:
        """更新智能体(仅创建者或管理员; 归属/内置标记不可改)"""
        agent = await self._get_for_manage(agent_id, user_id)
        await self.agent_dao.update(
            agent.id, AgentUpdate(**data.model_dump(exclude_unset=True))
        )

    async def delete(self, agent_id: str, user_id: str) -> None:
        """删除智能体(仅创建者或管理员; 内置不可删除)"""
        agent = await self._get_for_manage(agent_id, user_id)
        if agent.is_builtin:
            raise BusinessError("内置智能体不可删除")
        await self.agent_dao.delete(agent.id)

    async def _get_for_manage(self, agent_id: str, user_id: str) -> Agent:
        """获取待管理智能体并校验归属(创建者或管理员)"""
        agent = await self.agent_dao.get(agent_id)
        if not agent:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        if agent.created_by != user_id and not _is_admin(user_id):
            raise BusinessError("仅智能体创建者或管理员可操作")
        return agent
