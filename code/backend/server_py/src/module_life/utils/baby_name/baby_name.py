from module_life.utils.baby_name.do.baby_name import (
    NameInfoBase,
    NameInfoFull,
    NameInfoResultList,
    NameInfoResult,
    NameInfoPreference,
    NameInfoResultExplanation,
    NameInfoResultBase,
    NameInfoEX,
    NameInfoPredictFull,
)
from langgraph.graph import StateGraph, START, END
from langgraph.config import RunnableConfig, get_stream_writer
from langchain_core.language_models import BaseChatModel
from typing import Annotated
from typing_extensions import TypedDict
import datetime
from module_ai.utils.llm.do.llm_response import StreamOne
import logging

logger = logging.getLogger(__name__)


class BabyNameState(TypedDict):
    """LangGraph状态定义"""

    # NameInfoBase 字段
    birth_date: str = ""  # 出生日期
    birth_time: str = ""  # 出生时辰
    gender: str = ""  # 性别
    surname: str = ""  # 姓氏
    # NameInfoEX 字段
    name_length: int = 2  # 名字长度
    other: str = ""  # 补充信息
    # NameInfoPreference 字段
    wuxing_preference: list[str] = []  # 五行偏好
    constellation_preference: list[str] = []  # 星座偏好


async def calculate_wuxing_preference(
    state: BabyNameState, config: RunnableConfig
) -> list[str]:
    """根据出生日期计算五行偏好"""
    # 边流式输出给客户端，边收集完整结果用于后续节点”
    try:
        model: BaseChatModel = config.get("configurable", {}).get("model")
        # 问ai
        wuxing_pref = ""
        my_stream_writer = get_stream_writer()
        response_stream = model.astream(
            f"""
        出生日期: {state['birth_date']}
        出生时辰: {state['birth_time']}
        性别: {state['gender']}
        姓氏: {state['surname']}
        请根据以上信息，计算宝宝的五行偏好，输出简洁明了
        格式参考：
        ## 五行偏好: 
        ### 解释: 
        """
        )
        async for chunk in response_stream:
            if chunk.content:
                wuxing_pref += chunk.content
                my_stream_writer(
                    StreamOne(
                        content=chunk.content, node_name="calculate_wuxing_preference"
                    )
                )
        return {"wuxing_preference": wuxing_pref}
    except:
        raise ValueError("计算五行偏好失败")


async def calculate_constellation_preference(
    state: BabyNameState, config: RunnableConfig
) -> list[str]:
    """根据出生日期计算星座偏好"""
    try:
        model: BaseChatModel = config.get("configurable", {}).get("model")
        # 问ai
        constellation_pref = ""
        my_stream_writer = get_stream_writer()
        response_stream = model.astream(
            f"""
        出生日期: {state['birth_date']}
        出生时辰: {state['birth_time']}
        性别: {state['gender']}
        姓氏: {state['surname']}
        请根据以上信息，计算宝宝的星座偏好，输出简洁明了
        格式参考：
        ## 星座偏好: 
        ### 解释: 
        """
        )
        async for chunk in response_stream:
            if chunk.content:
                constellation_pref += chunk.content
                my_stream_writer(
                    StreamOne(
                        content=chunk.content,
                        node_name="calculate_constellation_preference",
                    )
                )
        return {"constellation_preference": constellation_pref}
    except:
        raise ValueError("计算星座偏好失败")


async def generate_name_result(state: BabyNameState, config: RunnableConfig) -> BabyNameState:
    """生成姓名结果"""
    logger.info("生成姓名结果")
    birth_date = state.get("birth_date", "")
    birth_time = state.get("birth_time", "")
    gender = state.get("gender", "")
    surname = state.get("surname", "")
    name_length = state.get("name_length", 2)
    other = state.get("other", "")
    wuxing_preference = state.get("wuxing_preference", [])
    constellation_preference = state.get("constellation_preference", [])
    #
    model: BaseChatModel = config.get("configurable", {}).get("model")
    # 问ai
    message = ""
    if wuxing_preference:
        message += f"五行偏好: {wuxing_preference}\n"
    if constellation_preference:
        message += f"星座偏好: {constellation_preference}\n"
    if other:
        message += f"补充信息: {other}\n"
    response_stream = model.astream(
        f"""
        出生日期: {birth_date}
        出生时辰: {birth_time}
        性别: {gender}
        姓氏: {surname}
        名字总长度: {name_length}
        {message}
        请根据以上信息，并考虑三才五格最佳组合，生成20个符合要求的宝宝姓名，每个姓名占一行,
        并给出每个姓名的以下几个方面解释（五行、三才五格、星座，以及姓名的含义），各个方面解释专业并尽量简短一些,不要输出多余的话和超过100字的分析
        输出格式为markdown格式且不要有```markdown```包裹
        严格按照以下格式输出:        
        ## **姓名1**
        五行:
        三才五格:
        星座:
        含义:
        
        ...
        
        ## **姓名10**
        五行:
        三才五格:
        星座:
        含义:
        
        ## 名字列表（总结确认符合五行，三才五格好的，并为每个名字打分）
        
        """
    )
    name_result = ""
    my_stream_writer = get_stream_writer()
    async for chunk in response_stream:
        if chunk.content:
            name_result += chunk.content
            my_stream_writer(
                StreamOne(
                    content=chunk.content,
                    node_name="generate_name_result",
                )
            )
    return {"name_result": name_result}


async def start(state: BabyNameState, config: RunnableConfig) -> BabyNameState:
    """启动流程"""
    # 执行图并返回结果
    return state


def create_baby_name_graph() -> StateGraph:
    """创建宝宝姓名生成的LangGraph流程图"""

    # 创建状态图
    workflow = StateGraph(BabyNameState)

    # 添加节点
    workflow.add_node("start", start)
    workflow.add_node("calculate_wuxing_preference", calculate_wuxing_preference)
    workflow.add_node(
        "calculate_constellation_preference", calculate_constellation_preference
    )
    workflow.add_node("generate_name_result", generate_name_result)

    # 设置流程
    # 同时生成五行偏好和星座偏好
    workflow.add_edge(START, "calculate_wuxing_preference")
    workflow.add_edge(START, "calculate_constellation_preference")
    workflow.add_edge("calculate_wuxing_preference", "generate_name_result")
    workflow.add_edge("calculate_constellation_preference", "generate_name_result")
    workflow.add_edge("generate_name_result", END)
    return workflow


class BabyNameStreamGenerator:
    """宝宝姓名流式生成器"""

    def __init__(self):
        self.graph = create_baby_name_graph().compile()

    async def generate_stream(
        self,
        name_info_predict_full: NameInfoPredictFull,
        model: BaseChatModel,
    ):
        """
        生成宝宝姓名的流式输出

        Args:
            birth_date: 出生日期
            birth_time: 出生时辰
            gender: 性别 ("boy" 或 "girl")
            surname: 姓氏

        Yields:
            流式输出结果
        """
        # 初始化状态
        initial_state = BabyNameState(
            birth_date=name_info_predict_full.birth_date,
            birth_time=name_info_predict_full.birth_time,
            gender=name_info_predict_full.gender,
            surname=name_info_predict_full.surname,
            name_length=name_info_predict_full.name_length,
            other=name_info_predict_full.other,
        )
        # 模型配置
        config = {"configurable": {"model": model}}
        # 执行图并流式输出
        async for chunk in self.graph.astream(
            initial_state,
            stream_mode="custom",
            config=config,
            version="v2",
        ):
            data:StreamOne|None = chunk.get("data")
            if data:
                print(data.content)
                yield data
            # if chunk["type"] == "messages":
            #     msg, metadata = chunk["data"]
            #     # 有content 才印
            #     if msg.content:
            #         node_name = metadata.get("langgraph_node", "")
            #         if node_name == "generate_name_result":
            #             continue
            #         content = msg.content
            #         print(content)

            #         yield StreamOne(content=content, node_name=node_name)


# 创建全局实例
baby_name_generator = BabyNameStreamGenerator()


# baby_name_generator.generate_stream(birth_date, gender, surname)
if __name__ == "__main__":
    from module_ai.service.llm_base import LLMBaseService
    import asyncio

    async def main():
        name_info_predict_full = NameInfoPredictFull(
            birth_date="",
            birth_time="",
            gender="boy",
            surname="王",
            name_length=3,
            other="""希望他一生平安，名字里有金属性字但不带金字旁""",
        )
        llm_base_service = LLMBaseService()
        model = await llm_base_service.get_llm("")
        async for chunk in baby_name_generator.generate_stream(
            name_info_predict_full, model
        ):
            pass

    asyncio.run(main())
