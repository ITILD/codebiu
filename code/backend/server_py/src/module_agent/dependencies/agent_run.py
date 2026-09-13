from fastapi import Depends

from module_ai.dependencies.llm import get_llm_service
from module_ai.service.llm import LLMService
from module_agent.service.agent_run import AgentRunService


async def get_agent_run_service(
    llm_service: LLMService = Depends(get_llm_service),
) -> AgentRunService:
    """获取智能体运行服务(复用 module_ai 的 LLM 基础服务注入)"""
    return AgentRunService(llm_service=llm_service)
