from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
# 1.准备参数
api_key = "sk-**"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model = "qwen3-4b"

# 2.创建模型实例
llm_base = ChatOpenAI(
    model=model,
    api_key=api_key,
    base_url=base_url,
    streaming=True,
    temperature=0.1,
)

if __name__ == "__main__":

    # 3.同步调用模型 时间
    import time
    messages = [HumanMessage(content="你好")]
    response = llm_base.invoke(messages)
    print(response.content)

    # 同步发3条
    start_time = time.time()
    for i in range(3):
        messages = [HumanMessage(content=f"你好{i}")]
        response = llm_base.invoke(messages)
        print(response.content)
    end_time = time.time()
    print(f"同步调用耗时: {end_time - start_time} 秒")  
    
    # 异步调用模型 时间
    start_time = time.time()
    # 4.异步调用模型
    async def async_call():
        messages = [HumanMessage(content="你好")]
        response = await llm_base.ainvoke(messages)
        print(response.content)
        
    # 异步并发3条
    async def async_call_3():
        tasks = [async_call() for _ in range(3)]
        await asyncio.gather(*tasks)
        
    # 5.调用异步函数
    import asyncio
    asyncio.run(async_call_3())
    end_time = time.time()
    print(f"异步调用耗时: {end_time - start_time} 秒")
