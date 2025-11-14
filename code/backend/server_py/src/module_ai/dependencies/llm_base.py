# LLM基础服务依赖注入
from module_ai.service.llm_base import LLMBaseService, llm_base_service


def get_llm_base_service():
    """
    获取LLM基础服务实例
    
    此函数作为FastAPI依赖项，提供对单例LLM基础服务的访问。
    由于LLMBaseService已通过单例模式实现，确保每次获取的是全局唯一实例。
    
    Returns:
        LLMBaseService实例
    """
    return llm_base_service