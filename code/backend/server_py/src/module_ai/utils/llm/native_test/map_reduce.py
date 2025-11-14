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
from config.ai import llm_chat, llm_embeddings,limiter_sim_chat


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


class MapReduce:
    """
    MapReduce 摘要流程的协调器
    """

    def __init__(
        self,
        token_max: int = 200,
        summaries_retries: int = 2,
        chunk_overlap_ratio: float = 0.1,
        llm=None,
    ):
        """
        初始化可配置的摘要系统

        参数:
            token_max: 每个文档块最大 token 数
            chunk_overlap_ratio: 重叠比例（默认 10%）
            summaries_retries: 最大合并重试次数
            llm: 使用的基础LLM或 CHAIN
        """
        self.app = None  # 编译后的 graph 应用
        self.token_max = token_max  # 最大 token 数
        self.summaries_retries = summaries_retries  # 摘要重试次数
        self.chunk_overlap = int(token_max * chunk_overlap_ratio)

        self.llm = llm
        self.splitter_utils = TextSplitterUtils(
            chunk_size=token_max / 2, chunk_overlap=token_max / 10
        )

    def _init_mapreduce_chain(self):
        # map
        map_prompt = ChatPromptTemplate.from_template("请简要总结以下内容：\n{content}")
        self.map_chain = map_prompt | self.llm
        # reduce
        reduce_prompt = ChatPromptTemplate.from_template(
            "请整合以下几段摘要并以中文输出：\n{doc_summaries}"
        )
        self.reduce_chain = reduce_prompt | self.llm

    def build(self):
        """
        构建并编译整个状态图，返回可调用的应用实例。
        """
        # 创建一个以 OverallState 为状态类型的图
        graph = StateGraph(OverallState)

        # 添加四个处理节点（函数）
        graph.add_node("generate_summary", self.generate_summary)  # 并行生成摘要
        graph.add_node("collect_summaries", self.collect_summaries)  # 收集所有摘要
        graph.add_node("collapse_summaries", self.collapse_summaries)  # 合并过长摘要
        graph.add_node(
            "generate_final_summary", self.generate_final_summary
        )  # 生成最终摘要

        # 添加边（流程控制逻辑）

        # 实现“一拆多”的 Map 操作  返回多个 Send，每个都会触发一次 generate_summary 执行
        graph.add_conditional_edges(START, self.map_summaries, ["generate_summary"])
        graph.add_edge("generate_summary", "collect_summaries")
        # 可能进入 collapse_summaries 或直接跳转到最终生成(根据 should_collapse 判断下一步)
        graph.add_conditional_edges("collect_summaries", self.should_collapse)
        # 形成递归循环，直到摘要足够短(判断是否还需继续压缩,更新并限制次数)
        graph.add_conditional_edges("collapse_summaries", self.should_collapse)
        # 最终摘要生成后，流程结束
        graph.add_edge("generate_final_summary", END)

        # 编译图
        self.app = graph.compile()

    def run(
        self,
        contents: List[str],
    ):
        if self.app is None:
            self.build()
        return self.app.ainvoke({"contents": contents})

    # 定义一个函数，用于计算一组文档的总 token 数
    def length_function(self, documents: List[Document]) -> int:
        """计算输入文档列表的总 token 数量"""
        # 对每个文档的内容调用 LLM 的 get_num_tokens 方法统计 token 数
        # 并求和返回
        return sum(LLMUtils.count_tokens(doc.page_content) for doc in documents)

    async def generate_summary(self, state: SummaryState):
        """
        文档内容生成摘要。
        """
        # 调用预定义的 map_chain（通常是用于摘要的 LLM 链）进行异步推理
        response = await self.map_chain.ainvoke(state["content"])
        # 返回结果，key 必须是 "summaries" 才能触发 operator.add 合并
        return {"summaries": [response]}

    def map_summaries(self, state: OverallState):
        """
        Map 阶段的并行处理，启动多个 generate_summary 任务。
        """
        return [
            # 每个 Send 表示启动一次 generate_summary 调用
            # 并传入 {"content": 当前文档内容}
            Send("generate_summary", {"content": content})
            for content in state["contents"]
        ]

    def collect_summaries(self, state: OverallState):
        """
        收集所有并行生成的摘要，并将它们转换为 Document 对象列表，存入 state["collapsed_summaries"]。
        """
        return {
            "collapsed_summaries": [
                # 把每个摘要字符串包装成 Document 对象
                Document(summary)
                for summary in state["summaries"]
            ]
        }

    async def collapse_summaries(self, state: OverallState):
        """
        合并过长的摘要（Reduce 阶段），但先确保每个文档都不超过 TOKEN_MAX
        """
        # Step 1: 检查每个摘要是否超长，如果超长则拆分成多个小块
        split_docs = []
        for doc in state["collapsed_summaries"]:
            num_tokens = LLMUtils.count_tokens(doc.page_content)
            if num_tokens > self.token_max:
                # 超长，拆分
                chunks = self.splitter_utils.split_text(doc.page_content)
                split_docs.extend(Document(chunk) for chunk in chunks)
            else:
                # 不超长，直接保留
                split_docs.append(doc)
        for doc in split_docs:
            print(LLMUtils.count_tokens(doc.page_content))

        # Step 2: 现在确保所有文档都 <= token_max，再调用 split_list_of_docs
        doc_lists = split_list_of_docs(
            split_docs,
            self.length_function,
            self.token_max,
        )

        results = []
        tasks = []
        for doc_list in doc_lists:
            collapsed = await acollapse_docs(doc_list, self.reduce_chain.ainvoke)
            results.append(collapsed)

        return {"collapsed_summaries": results}

    def should_collapse(
        self,
        state: OverallState,
    ) -> Literal["collapse_summaries", "generate_final_summary"]:
        """
        决定下一步是继续合并摘要，还是可以直接生成最终摘要。
        """
        num_tokens = self.length_function(state["collapsed_summaries"])
        collapse_attempts = state.get("collapse_attempts", 0)
        collapse_attempts += 1
        if collapse_attempts >= self.summaries_retries:
            return "generate_final_summary"

        if num_tokens > self.token_max:
            return "collapse_summaries"  # 继续压缩
        else:
            return "generate_final_summary"  # 可以输出最终结果

    async def generate_final_summary(self, state: OverallState):
        """
        当所有中间摘要已经足够短时，调用 reduce_chain 生成最终摘要。

        参数:
            state["collapsed_summaries"]: 当前所有摘要（已压缩到安全长度）

        返回:
            dict: 包含最终摘要的字段 {"final_summary": "..."}
        """
        # 调用 reduce_chain 处理所有剩余摘要，生成一条最终总结
        response = await self.reduce_chain.ainvoke(state["collapsed_summaries"])
        return {"final_summary": response}


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
        contents = [
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
        result = await app.ainvoke(inputs)
        print("最终摘要：", result["final_summary"])

    asyncio.run(main())
