"""模型工厂: 模型配置 -> LangChain 模型实例

- config: 模型调用参数模板(默认参数/成本/上下文窗口, 与 do.model_config 的 DB 实体区分)
- builder: 按配置构建 chat/embeddings 模型实例(build_model 为统一入口)
"""
from module_ai.utils.llm.factory.builder import build_chat_model, build_embeddings, build_model

__all__ = ["build_model", "build_chat_model", "build_embeddings"]
