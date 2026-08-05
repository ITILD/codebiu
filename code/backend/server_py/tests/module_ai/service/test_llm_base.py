
import pytest
import asyncio
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from common.config.index import conf
from module_ai.service.llm_base import LLMBaseService, ModelConfigCreateRequest, ModelType, ModelServerType

@pytest.mark.asyncio
async def test_llm_chat():
    llm_service = LLMBaseService()
    #
    model_config_create_request = ModelConfigCreateRequest(
        model_type=ModelType.CHAT,
        server_type=ModelServerType.OPENAI,
        model="qwen3.6-27b",
        # model="qwen3-8b",
        # model="glm-5.2",
        # model="qwen3.7-max-preview",
        # model="qwen3-8b",
        api_key=conf.test.llm_out_0.api_key,
        url=conf.test.llm_out_0.base_url,
        streaming=True,
        # no_think = True
    )

    llm_chain = llm_service._llm_by_config(model_config_create_request)
    messages = [SystemMessage(content="你是一个不废话的AI助手"), HumanMessage(content="一句话算出1+1=？")]
    responses = llm_chain.astream(messages)
    async for response in responses:
        if hasattr(response, "reasoning_content"):
            print('think_:',response.reasoning_content)
        elif hasattr(response, "content"):
            print(response.content)

@pytest.mark.asyncio
async def test_llm_embed():
    llm_service = LLMBaseService()
    model_config_create_request = ModelConfigCreateRequest(
        model_type=ModelType.EMBEDDINGS,
        server_type=ModelServerType.OPENAI,
        model="/models/jina-embeddings-v5-text-small",
        # model="text-embedding-v4",
        # model="qwen3-8b",
        api_key="not-needed",
        url=conf.test.llm_1.base_url,
        out_tokens = 1024
    )

    llm_chain = llm_service._llm_by_config(model_config_create_request)
    aembed_result = llm_chain.embed_query("1")
    print(len(aembed_result))

@pytest.mark.asyncio
async def test_llm_embed_local():
    import requests

    payload = {
        "model": "/models/jina-embeddings-v5-text-small",
        "input": ["今天天气很好"],
        "extra_body": {"input_type": "query"}
    }

    r = requests.post(conf.test.llm_1.base_url+"/embeddings", json=payload)
    print(r.json())

@pytest.mark.asyncio
async def test_llm_embed_local2():
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(
        model="/models/jina-embeddings-v5-text-small",
        api_key="not-needed",
        base_url=conf.test.llm_1.base_url,
    )

    # 单条
    vec = embeddings.embed_query("今天天气真好")
    print(f"向量维度: {len(vec)}")

    # 批量
    texts = ["文本A", "文本B", "文本C"]
    vecs = embeddings.embed_documents(texts)
    print(f"批量向量数: {len(vecs)}")

if __name__ == "__main__":
    # asyncio.run(test_llm_chat())
    asyncio.run(test_llm_embed())
    # asyncio.run(test_llm_embed_local())
    # asyncio.run(test_llm_embed_local2())
