"""智能体运行服务(原 module_data_clean 清洗链路并入: 按智能体结构体配置执行一次输入→输出)

- simple 类型: agent.system_prompt 作为任务/清洗提示词(系统角色), 输入数据与结构要求作为用户消息
- workflow 类型: 交给 WorkflowService 按图执行, 节点轨迹随运行历史落库
- output_type=json 时优先 with_structured_output 严格按 Schema, 失败回退提示词约束 + 容错解析
- 运行记录写入 agent_run 历史表(仅本人可见; 工作流失败也落库便于排查)
"""

import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from module_ai.service.llm import LLMService
from common.utils.db.schema.pagination import PaginationParams, PaginationResponse
from common.utils.fastapiEX.exceptions import BusinessError, ForbiddenError, NotFoundError
from module_agent.dao.agent import AgentDao
from module_agent.dao.agent_run import AgentRunDao
from module_agent.do.agent import Agent, AgentIOType, AgentType
from module_agent.do.agent_run import AgentRun, AgentRunHistory, AgentRunRequest, AgentRunResponse
from module_agent.service.workflow import (
    NodeTrace,
    WorkflowExecuteError,
    WorkflowService,
    parse_json_content,
)

logger = logging.getLogger(__name__)

# 运行系统角色提示词(沿用原数据清洗的语义, 叠加 agent 自身提示词)
RUN_SYSTEM_PROMPT = (
    "你是一名数据处理助手, 负责根据智能体配置的任务提示词, "
    "对输入的数据(JSON 或文本)进行处理并按要求的结构输出。\n"
    "要求:\n"
    "1. 严格遵循任务提示词执行, 不要添加与任务无关的内容;\n"
    "2. 保持数据语义不变, 仅按任务要求做格式、噪声、冗余与一致性处理;\n"
    "3. 输出只包含处理结果, 不要输出解释或 Markdown 代码块标记。"
)


class AgentRunService:
    """智能体运行服务(结构体配置驱动的单次执行 + 运行历史)"""

    def __init__(
        self,
        agent_dao: AgentDao | None = None,
        run_dao: AgentRunDao | None = None,
        llm_service: LLMService | None = None,
        workflow_service: WorkflowService | None = None,
    ):
        """依赖注入构造器:初始化所需的数据访问对象与 LLM 基础服务"""
        self.agent_dao = agent_dao or AgentDao()
        self.run_dao = run_dao or AgentRunDao()
        self.llm_service = llm_service
        self.workflow_service = workflow_service or WorkflowService(llm_service=self.llm_service)

    async def run(
        self, agent_id: str, user_id: str, request: AgentRunRequest
    ) -> AgentRunResponse:
        """执行一次运行: 校验可访问性 → 按类型分流(工作流/简单) → 持久化运行历史"""
        agent = await self.agent_dao.get(agent_id)
        if not agent:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        if not agent.is_public and agent.created_by != user_id:
            raise ForbiddenError("仅公共智能体或本人创建的智能体可运行")

        # 工作流智能体: 图执行 + 轨迹(不走简单的单次 LLM 链路)
        if agent.agent_type == AgentType.WORKFLOW:
            return await self._run_workflow_agent(agent, user_id, request)

        llm: BaseChatModel | None = await self.llm_service.get_llm(
            request.model_id, streaming=False
        )
        if llm is None:
            raise NotFoundError("模型配置不存在或不可用")

        messages = self._build_messages(agent, request.input)
        if agent.output_type == AgentIOType.JSON:
            result = await self._run_json(llm, messages, agent.output_schema)
        else:
            result = await self._run_string(llm, messages)

        run_id = await self.run_dao.add(
            AgentRun(
                agent_id=agent.id,
                user_id=user_id,
                model_id=request.model_id,
                input=request.input,
                output=result,
            )
        )
        return AgentRunResponse(run_id=run_id, result=result)

    async def _run_workflow_agent(
        self, agent: Agent, user_id: str, request: AgentRunRequest
    ) -> AgentRunResponse:
        """工作流智能体执行: 图驱动 + 轨迹落库(失败也落库, 便于排查后重试)"""
        try:
            result, traces = await self.workflow_service.run_workflow(agent, request)
        except WorkflowExecuteError as e:
            logger.warning(f"工作流执行失败(agent={agent.id}): {e}")
            traces = e.traces
            result = {"error": str(e)}
            await self.run_dao.add(
                AgentRun(
                    agent_id=agent.id,
                    user_id=user_id,
                    model_id=request.model_id,
                    input=request.input,
                    output=result,
                    trace=self._trace_payload(traces),
                )
            )
            raise BusinessError(f"工作流执行失败: {e}") from e

        run_id = await self.run_dao.add(
            AgentRun(
                agent_id=agent.id,
                user_id=user_id,
                model_id=request.model_id,
                input=request.input,
                output=result,
                trace=self._trace_payload(traces),
            )
        )
        return AgentRunResponse(
            run_id=run_id, result=result, trace=[t.model_dump() for t in traces]
        )

    @staticmethod
    def _trace_payload(traces: list[NodeTrace]) -> dict:
        """轨迹序列化为 JSONB 存储结构"""
        return {"nodes": [t.model_dump() for t in traces]}

    async def list_runs(
        self, agent_id: str, user_id: str, pagination: PaginationParams
    ) -> PaginationResponse:
        """分页获取本人运行历史(按运行时间倒序; 智能体不存在时 404)"""
        agent = await self.agent_dao.get(agent_id)
        if not agent:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        items = await self.run_dao.list_by_agent_user(
            agent_id, user_id, pagination.offset, pagination.limit
        )
        total = await self.run_dao.count_by_agent_user(agent_id, user_id)
        history = [
            AgentRunHistory(
                id=item.id,
                agent_id=item.agent_id,
                model_id=item.model_id,
                input=item.input,
                output=item.output,
                trace=item.trace,
                created_at=item.created_at,
            )
            for item in items
        ]
        return PaginationResponse.create(history, total, pagination)

    async def get_run_detail(
        self, agent_id: str, run_id: str, user_id: str
    ) -> AgentRunHistory:
        """查询单条运行详情(含工作流节点轨迹; 仅本人记录, 智能体/记录不存在时 404)"""
        agent = await self.agent_dao.get(agent_id)
        if not agent:
            raise NotFoundError(f"未找到ID为 {agent_id} 的智能体")
        run = await self.run_dao.get_run(run_id, user_id)
        if not run or run.agent_id != agent_id:
            raise NotFoundError(f"未找到运行记录 {run_id}")
        return AgentRunHistory(
            id=run.id,
            agent_id=run.agent_id,
            model_id=run.model_id,
            input=run.input,
            output=run.output,
            trace=run.trace,
            created_at=run.created_at,
        )

    @staticmethod
    def _build_messages(agent: Agent, input_data: Any) -> list:
        """构造 LLM 消息: 系统角色(运行约束+agent 提示词) + 用户内容(输入/结构要求)"""
        data_text = (
            json.dumps(input_data, ensure_ascii=False, indent=2)
            if not isinstance(input_data, str)
            else input_data
        )
        user_content = [f"### 任务提示词\n{agent.system_prompt}", f"### 输入数据\n{data_text}"]
        if agent.input_type == AgentIOType.JSON and agent.input_schema:
            schema_text = json.dumps(agent.input_schema, ensure_ascii=False, indent=2)
            user_content.append(
                f"### 输入结构说明(输入数据应符合此 JSON Schema)\n{schema_text}"
            )
        if agent.output_type == AgentIOType.JSON:
            if agent.output_schema:
                schema_text = json.dumps(agent.output_schema, ensure_ascii=False, indent=2)
                user_content.append(
                    f"### 输出结构要求(必须严格遵循此 JSON Schema)\n{schema_text}"
                )
            else:
                user_content.append(
                    "### 输出结构要求\n输出合法的 JSON(对象或数组), 不要包含 Markdown 代码块标记。"
                )
        return [
            SystemMessage(content=RUN_SYSTEM_PROMPT),
            HumanMessage(content="\n\n".join(user_content)),
        ]

    @staticmethod
    async def _run_string(llm: BaseChatModel, messages: list) -> str:
        """字符串输出: 直接返回模型文本结果"""
        response = await llm.ainvoke(messages)
        content = response.content
        return content if isinstance(content, str) else json.dumps(
            content, ensure_ascii=False
        )

    @classmethod
    async def _run_json(cls, llm: BaseChatModel, messages: list, output_schema: dict | None):
        """JSON 输出: 优先结构化输出(严格按 Schema), 失败回退为提示词约束 + 解析"""
        if output_schema:
            try:
                structured_llm = llm.with_structured_output(output_schema)
                return await structured_llm.ainvoke(messages)
            except Exception as e:
                logger.warning(f"结构化输出失败, 回退提示词解析: {e}")
        response = await llm.ainvoke(messages)
        return parse_json_content(response.content)
