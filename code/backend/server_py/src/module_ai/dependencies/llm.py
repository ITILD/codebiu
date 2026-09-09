# LLM 服务依赖注入
from module_ai.service.llm import LLMService

# 全局服务实例(通过单例模式确保全局唯一)
llm_service = LLMService()

def get_llm_service():
    """
    获取LLM服务实例

    此函数作为FastAPI依赖项，提供对单例LLM服务的访问。
    由于LLMService已通过单例模式实现，确保每次获取的是全局唯一实例。

    Returns:
        LLMService实例
    """
    return llm_service