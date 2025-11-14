# 导入必要的模块
import operator  # 用于状态合并操作（如列表拼接）
from typing import Annotated, List, Literal, TypedDict  # 类型提示支持

# 从 LangChain 导入文档合并相关的异步工具函数
from langchain.chains.combine_documents.reduce import (
    acollapse_docs,  # 异步合并一组文档（reduce 操作）
    split_list_of_docs,  # 根据 token 数量将文档列表拆分成多个小组
)

# Document：LangChain 中表示文本内容的基本数据结构
from langchain_core.documents import Document

# Send：LangGraph 中用于动态分发任务的关键对象
from langgraph.constants import Send

# StateGraph：构建状态驱动工作流的核心类
# START / END：图的起始与结束节点标识
from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# 设定最大允许 token 数量为 1000
from module_ai.utils.llm.common_splitter.text_splitter_utils import TextSplitterUtils
from module_ai.utils.llm.utils.llm_utils import LLMUtils
from config.ai import llm_chat, llm_embeddings



TOKEN_MAX = 200  # 最大 token 数
SUMMARIES_RETRYS = 2  # 摘要重试次数
CHUNK_OVERLAP = int(TOKEN_MAX * 0.1)


map_prompt = ChatPromptTemplate.from_template("请简要总结以下内容：{content}")
map_chain = map_prompt | llm_chat

# 
reduce_prompt = ChatPromptTemplate.from_template( "请整合以下几段摘要并以中文输出：\n\n{doc_summaries}" )
reduce_prompt = ChatPromptTemplate([("human", "以下是若干段daima1： {docs} 请将这些内容进行提炼整合，生成一段最终的、统一的总结， 概括其中的主要主题。")])
reduce_chain = reduce_prompt | llm_chat


# 定义一个函数，用于计算一组文档的总 token 数
def length_function(documents: List[Document]) -> int:
    """计算输入文档列表的总 token 数量"""
    # 对每个文档的内容调用 LLM 的 get_num_tokens 方法统计 token 数
    # 并求和返回
    return sum(LLMUtils.count_tokens(doc.page_content) for doc in documents)

class OverallState(TypedDict):
    """
    整个图的状态容器 主图的状态结构，包含整个流程所需的所有数据。
    """

    # 原始输入的多个文档内容（字符串列表）
    contents: List[str]

    # 存放所有生成的中间摘要（使用 operator.add 实现自动累加合并）
    # 每次 generate_summary 返回的摘要都会被 "+=" 追加到这里
    summaries: Annotated[list, operator.add]

    # 当前待处理的摘要文档列表（Document 类型），用于递归合并
    collapsed_summaries: List[Document]

    # 最终生成的综合摘要结果
    final_summary: str
    
    # 记录当前已经尝试合并摘要的次数
    collapse_attempts: Annotated[int, operator.add] = 0

class SummaryState(TypedDict):
    """
    单个摘要生成任务的状态。
    每个并行执行的 generate_summary 只需要接收一段文本内容。
    """

    content: str  # 一篇原始文档的内容


async def generate_summary(state: SummaryState):
    """
    接收一个文档内容，调用 map_chain 生成摘要。

    参数:
        state (SummaryState): 包含单个文档内容的字典，如 {"content": "..."}

    返回:
        dict: 包含新摘要的字典，格式为 {"summaries": [新摘要]}
              因为 summaries 字段是 Annotated[..., operator.add]，
              所以这个新摘要会被自动追加到 overall state 的 summaries 列表中。
    """
    # 调用预定义的 map_chain（通常是用于摘要的 LLM 链）进行异步推理
    response = await map_chain.ainvoke(state["content"])
    # 返回结果，key 必须是 "summaries" 才能触发 operator.add 合并
    return {"summaries": [response]}

def map_summaries(state: OverallState):
    """
    动态边函数：根据原始文档数量，创建多个并行任务。

    作用：
        - 遍历 state["contents"] 中的每一篇文档
        - 为每篇文档创建一个 Send 对象，发送到 "generate_summary" 节点
        - 实现 Map 阶段的并行处理

    返回:
        List[Send]: 一组 Send 指令，LangGraph 会据此分发任务
    """
    return [
        # 每个 Send 表示启动一次 generate_summary 调用
        # 并传入 {"content": 当前文档内容}
        Send("generate_summary", {"content": content})
        for content in state["contents"]
    ]

def collect_summaries(state: OverallState):
    """
    将所有已生成的字符串摘要（state["summaries"]）转换为 Document 对象列表，
    存入 collapsed_summaries，准备进入 Reduce 阶段。

    返回:
        dict: 更新后的 collapsed_summaries 字段
    """
    return {
        "collapsed_summaries": [
            # 把每个摘要字符串包装成 Document 对象
            Document(summary)
            for summary in state["summaries"]
        ]
    }

splitter_utils = TextSplitterUtils(chunk_size=TOKEN_MAX/2, chunk_overlap=TOKEN_MAX/10)
async def collapse_summaries(state: OverallState):
    """
    合并过长的摘要（Reduce 阶段），但先确保每个文档都不超过 TOKEN_MAX
    """
    # Step 1: 检查每个摘要是否超长，如果超长则拆分成多个小块
    split_docs = []
    for doc in state["collapsed_summaries"]:
        num_tokens = LLMUtils.count_tokens(doc.page_content)
        if num_tokens > TOKEN_MAX:
            # 超长，拆分
            chunks = splitter_utils.split_text(doc.page_content)
            split_docs.extend(Document(chunk) for chunk in chunks)
        else:
            # 不超长，直接保留
            split_docs.append(doc)
    for doc in split_docs:
        print(LLMUtils.count_tokens(doc.page_content))

    # Step 2: 现在确保所有文档都 <= token_max，再调用 split_list_of_docs
    doc_lists = split_list_of_docs(
        split_docs,
        length_function,
        TOKEN_MAX,
    )

    results = []
    for doc_list in doc_lists:
        collapsed = await acollapse_docs(doc_list, reduce_chain.ainvoke)
        results.append(collapsed)

    return {"collapsed_summaries": results}


# ======================================================================================
# 条件边函数：should_collapse —— 判断是否需要继续合并摘要
# ======================================================================================
def should_collapse(
    state: OverallState,
) -> Literal["collapse_summaries", "generate_final_summary"]:
    """
    决定下一步是继续合并摘要，还是可以直接生成最终摘要。

    逻辑：
        - 如果当前摘要总 token 数 > TOKEN_MAX → 继续合并（走 collapse_summaries）
        - 否则 → 已足够短，可生成最终摘要（走 generate_final_summary）

    返回:
        下一个节点名称（字符串）
    """
    num_tokens = length_function(state["collapsed_summaries"])
    collapse_attempts = state.get("collapse_attempts", 0)
    collapse_attempts += 1
    if collapse_attempts >= SUMMARIES_RETRYS:
        return "generate_final_summary"
    
    if num_tokens > TOKEN_MAX:
        return "collapse_summaries"  # 继续压缩
    else:
        return "generate_final_summary"  # 可以输出最终结果


# ======================================================================================
# 节点函数 4：generate_final_summary —— 生成最终的综合摘要
# ======================================================================================
async def generate_final_summary(state: OverallState):
    """
    当所有中间摘要已经足够短时，调用 reduce_chain 生成最终摘要。

    参数:
        state["collapsed_summaries"]: 当前所有摘要（已压缩到安全长度）

    返回:
        dict: 包含最终摘要的字段 {"final_summary": "..."}
    """
    # 调用 reduce_chain 处理所有剩余摘要，生成一条最终总结
    response = await reduce_chain.ainvoke(state["collapsed_summaries"])
    return {"final_summary": response}


# ======================================================================================
# 构建状态图（StateGraph）
# ======================================================================================
async def setup_graph():
    """
    构建并编译整个状态图，返回可调用的应用实例。
    """

    # 创建一个以 OverallState 为状态类型的图
    graph = StateGraph(OverallState)

    # 添加四个处理节点（函数）
    graph.add_node("generate_summary", generate_summary)  # 并行生成摘要
    graph.add_node("collect_summaries", collect_summaries)  # 收集所有摘要
    graph.add_node("collapse_summaries", collapse_summaries)  # 合并过长摘要
    graph.add_node("generate_final_summary", generate_final_summary)  # 生成最终摘要

    # 添加边（流程控制逻辑）

    # 从 START 开始，调用 map_summaries 函数
    # 它返回多个 Send，每个都会触发一次 generate_summary 执行
    # 实现“一拆多”的 Map 操作
    graph.add_conditional_edges(START, map_summaries, ["generate_summary"])

    # 所有 generate_summary 完成后，统一进入 collect_summaries
    graph.add_edge("generate_summary", "collect_summaries")

    # collect_summaries 后，根据 should_collapse 判断下一步
    # 可能进入 collapse_summaries 或直接跳转到最终生成
    graph.add_conditional_edges("collect_summaries", should_collapse)

    # collapse_summaries 执行完后，再次判断是否还需继续压缩
    # 形成递归循环，直到摘要足够短
    graph.add_conditional_edges("collapse_summaries", should_collapse)

    # 最终摘要生成后，流程结束
    graph.add_edge("generate_final_summary", END)

    # 编译图，得到可调用的应用实例
    app = graph.compile()
    return app


if __name__ == "__main__":
    # ======================================================================================
    # ✅ 使用说明（示例）
    # ======================================================================================
    """
    # 假设你已经定义好了：
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    map_prompt = PromptTemplate.from_template("请简要总结以下内容：{content}")
    map_chain = LLMChain(llm=llm, prompt=map_prompt)

    reduce_prompt = PromptTemplate.from_template("请整合以下几段摘要：\n\n{doc_summaries}")
    reduce_chain = StuffDocumentsChain(..., prompt=reduce_prompt, ...)
    """
    import asyncio
    

    async def main():
        app = await setup_graph()
        # 输入多篇文档内容
        inputs = {
            "contents": [
                """传统的三幕结构包括以下部分：

第一幕——设定：提示，诱发事件，第一个情节点
第二幕——冲突：上升的行动，中点，第二个情节点
第三幕——结局：预高潮，高潮，收场
每一幕中都有一些不同的“节拍”——一个情节事件。亚里士多德首先发明了通过三个部分讲故事的方式，每一幕都应该由一个节拍来衔接，将叙事引向不同的方向。在《诗学》中，他认为故事必须是一连串的因果节拍：每个场景必须引出下一个发生的事情，而不是一个独立的“事件”。""",
                """如何使用三幕结构？
很明显，很多作家都同意，在讲故事的时候，“好事成三”。我们已经有了三幕的大框架，我们需要进一步把每一幕再分成三个“节拍”。以下将以《绿野仙踪》和《饥饿游戏》作为分析实例，来研究三幕结构是如何应用到故事当中的。""",
                """2. 诱发事件
这是让主人公开启冒险行动的催化剂。诱发事件是三幕故事结构中的一个关键环节：没有它，接下来的故事就不会存在。诱发事件向主人公提出了一个登上旅程的原因——一个可以帮助他们改变处境和实现目标的旅程。

在设计诱发事件的时候，问自己以下问题：

主人公对他们的生活有哪些不满？
要怎样才能让主人公找到满足感？(这就是他们的目标）
主人公最大的恐惧和性格缺陷是什么？
主人公为找到满足感而需要采取的行动将如何迫使他们直面自己的恐惧和性格缺陷？""",
            ]
        }
        result = await app.ainvoke(inputs)
        print("最终摘要：", result["final_summary"])

    asyncio.run(main())
