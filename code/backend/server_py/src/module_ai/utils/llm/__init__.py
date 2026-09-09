"""LLM 工具包(文本类大模型: chat/embeddings/rerank)

按功能子包组织:
    - types:    全局类型枚举(ModelType/ModelServerType/RoleType/StreamStatus...)
    - factory:  模型工厂(调用参数模板 config + LangChain 实例构建 builder)
    - chat:     对话链路工具(think 思考模型 / trim 消息裁剪 / parsers token限制 / utils 计数)
    - stream:   流式输出(SSE 事件流生成器 + 流式响应 schema)
    - token:    token 计数(tiktoken + transformers)
    - prompts:  提示词模板
    - rerank:   重排序工具包(interface + 各服务端 impl)
    - splitter: 文本切分工具包
    - model_load: 本地模型下载/加载/测试
    - native_test: 原生调用实验脚本

本包 __init__ 刻意保持为空(仅文档), 使用方请按需从具体子模块导入, 例如:

    from module_ai.utils.llm.types import ModelType
    from module_ai.utils.llm.factory.builder import build_model
    from module_ai.utils.llm.stream.sse import event_generator
"""
