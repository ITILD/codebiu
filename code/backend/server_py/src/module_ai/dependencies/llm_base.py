# LLM基础服务依赖注入
from module_ai.service.llm_base import LLMBaseService
from module_ai.dao.llm_base_prompt import LLMBasePrompt
# from fastapi import Depends

def get_llm_base_prompt():
    """
    获取LLM基础提示实例
    
    此函数作为FastAPI依赖项，提供对LLM基础提示的访问。
    
    Returns:
        LLMBasePrompt实例
    """
    return LLMBasePrompt()

# 全局服务实例(通过单例模式确保全局唯一)
llm_base_service = LLMBaseService()

def get_llm_base_service():
    """
    获取LLM基础服务实例
    
    此函数作为FastAPI依赖项，提供对单例LLM基础服务的访问。
    由于LLMBaseService已通过单例模式实现，确保每次获取的是全局唯一实例。
    
    Returns:
        LLMBaseService实例
    """
    return llm_base_service