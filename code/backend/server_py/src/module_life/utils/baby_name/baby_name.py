"""宝宝起名生成器(LangGraph 流程)

流程设计:
1. 严格计算节点(纯程序, 非选中的自动跳过):
   - calc_wuxing: 干支四柱 + 五行统计 + 喜用神(扶抑法)
   - calc_constellation: 公历严格划分星座
   - calc_zodiac: 立春分界生肖 + 宜用字根
   - calc_tarot: 生命灵数 → 生命塔罗牌
   计算结果实时推送前端(node_name=calc_*), 同时汇总注入起名提示词。
2. generate_name_result: LLM 结合宝宝信息 + 严格计算结果 + 风格类参考
   (基督/佛教/道教等文化约束)流式生成候选名字。
3. finalize: 解析 LLM 输出中的名字清单, 程序计算每个名字的三才五格评分,
   以结构化 JSON 推送(node_name=names_evaluated), 供前端渲染名字卡片。
"""

import json
import logging
import re
from typing import Annotated
from typing_extensions import TypedDict

from langgraph.config import RunnableConfig, get_stream_writer
from langgraph.graph import StateGraph, START, END
from langchain_core.language_models import BaseChatModel

from module_ai.utils.llm.stream.schemas import StreamOne
from module_life.utils.baby_name.almanac import ZODIAC_HINTS, get_zodiac
from module_life.utils.baby_name.constellation import get_constellation
from module_life.utils.baby_name.do.baby_name import NameInfoPredictFull
from module_life.utils.baby_name.folklore import (
    FOLK_REFERENCES,
    ReferenceEnum,
)
from module_life.utils.baby_name.sancai import evaluate_name
from module_life.utils.baby_name.strokes import stroke_of
from module_life.utils.baby_name.tarot import get_tarot
from module_life.utils.baby_name.wuxing import analyze_wuxing

logger = logging.getLogger(__name__)

# 严格计算型参考 → 计算函数注册(选中的才执行)
STRICT_REFERENCES = [
    ReferenceEnum.WUXING,
    ReferenceEnum.SANCAI,
    ReferenceEnum.CONSTELLATION,
    ReferenceEnum.ZODIAC,
    ReferenceEnum.TAROT,
]


def _merge_dict(left: dict | None, right: dict | None) -> dict:
    """并行节点写同一 dict 键的合并 reducer(LangGraph 并行分支每步只允许一个值)"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class BabyNameState(TypedDict, total=False):
    """LangGraph状态定义"""

    # 宝宝信息
    birth_date: str  # 出生日期(公历)
    birth_time: str  # 出生时辰
    gender: str  # 性别
    surname: str  # 姓氏
    name_length: int  # 名字长度
    other: str  # 补充要求
    # 起名配置
    references: list[str]  # 选中的参考体系
    count: int  # 生成数量
    exclude_names: list[str]  # 需避开的历史名字
    # 中间结果
    calc_texts: Annotated[dict[str, str], _merge_dict]  # 各严格参考的计算结果文本(key=参考key)
    name_markdown: str  # LLM 生成的名字 markdown


def _gender_label(gender: str) -> str:
    return {"boy": "男宝", "girl": "女宝", "unknown": "未知"}.get(gender, "未知")


# ==================== 严格计算节点(纯程序, 无需 LLM) ====================

async def calc_wuxing(state: BabyNameState, config: RunnableConfig) -> dict:
    """五行八字: 干支四柱+五行统计+喜用神(经典扶抑法)"""
    if ReferenceEnum.WUXING not in state.get("references", []):
        return {}
    result = analyze_wuxing(state["birth_date"], state["birth_time"])
    lines = ["### 五行八字(经典干支推算)", ""]
    for label, name in zip(result["pillar_labels"], result["pillar_names"]):
        lines.append(f"- **{label}**: {name}")
    counts = result["counts"]
    lines.append(f"- **五行分布**: {'、'.join(f'{k}{v}' for k, v in counts.items())}")
    if result["canggan"]:
        hidden = "；".join(f"{c['pillar']}{c['branch']}藏{c['hidden']}" for c in result["canggan"])
        lines.append(f"- **地支藏干**: {hidden}")
    lines.append(
        f"- **日主**: {result['day_master']}({result['strength']})"
    )
    lines.append(f"- **喜用**: {'、'.join(result['favorable'])}")
    text = "\n".join(lines)
    writer = get_stream_writer()
    writer(StreamOne(content=text, node_name="calc_wuxing"))
    return {"calc_texts": {**state.get("calc_texts", {}), "wuxing": text}}


async def calc_constellation(state: BabyNameState, config: RunnableConfig) -> dict:
    """星座: 公历日期严格划分"""
    if ReferenceEnum.CONSTELLATION not in state.get("references", []):
        return {}
    info = get_constellation(state["birth_date"])
    text = (
        "### 星座(公历严格划分)\n\n"
        f"- **星座**: {info.name}({info.date_range})\n"
        f"- **元素**: {info.element}象星座\n"
        f"- **特质**: {info.traits}"
    )
    writer = get_stream_writer()
    writer(StreamOne(content=text, node_name="calc_constellation"))
    return {"calc_texts": {**state.get("calc_texts", {}), "constellation": info.summary()}}


async def calc_zodiac(state: BabyNameState, config: RunnableConfig) -> dict:
    """生肖: 立春分界 + 宜用字根"""
    if ReferenceEnum.ZODIAC not in state.get("references", []):
        return {}
    zodiac = get_zodiac(state["birth_date"])
    hint = ZODIAC_HINTS.get(zodiac, "")
    text = (
        "### 生肖(立春分界)\n\n"
        f"- **生肖**: {zodiac}\n"
        f"- **宜用字根**: {hint}"
    )
    writer = get_stream_writer()
    writer(StreamOne(content=text, node_name="calc_zodiac"))
    return {"calc_texts": {**state.get("calc_texts", {}), "zodiac": f"生肖{zodiac}。宜用字根: {hint}"}}


async def calc_tarot(state: BabyNameState, config: RunnableConfig) -> dict:
    """塔罗牌: 生命灵数推算"""
    if ReferenceEnum.TAROT not in state.get("references", []):
        return {}
    info = get_tarot(state["birth_date"])
    text = (
        "### 塔罗牌(生命灵数推算)\n\n"
        f"- **生命灵数**: {info['number']}\n"
        f"- **生命塔罗牌**: {info['card']}\n"
        f"- **牌意**: {info['meaning']}"
    )
    writer = get_stream_writer()
    writer(StreamOne(content=text, node_name="calc_tarot"))
    return {"calc_texts": {**state.get("calc_texts", {}), "tarot": info["summary"]}}


# ==================== LLM 起名节点 ====================

def _build_prompt(state: BabyNameState) -> str:
    """组装起名提示词: 宝宝信息 + 严格计算结果 + 风格类参考约束"""
    refs = state.get("references", [])
    gender = _gender_label(state.get("gender", "unknown"))
    name_length = state.get("name_length", 2)
    count = state.get("count", 20)
    exclude = state.get("exclude_names", [])

    prompt = f"""你是一位精通中国传统姓名学与多文化起名的资深起名师。请为宝宝起名。

## 宝宝信息
- 姓氏: {state.get('surname', '')}
- 性别: {gender}
- 出生日期(公历): {state.get('birth_date', '')}
- 出生时辰: {state.get('birth_time', '')}
- 名字字数(不含姓): {name_length}
"""

    # 严格计算结果(程序精确推算, 必须遵循)
    calc_texts = state.get("calc_texts", {})
    if calc_texts:
        prompt += "\n## 民俗推算结果(经典算法程序计算, 起名必须遵循)\n"
        for key, text in calc_texts.items():
            prompt += f"\n{text}\n"
        if ReferenceEnum.WUXING in refs and "wuxing" in calc_texts:
            prompt += "\n注意: 名字用字的五行属性应优先补益上述喜用五行(按偏旁、部首或字义判断)。\n"

    # 风格类参考(文化约束)
    style_refs = [FOLK_REFERENCES[r] for r in refs if r in FOLK_REFERENCES and not FOLK_REFERENCES[r].strict]
    if style_refs:
        prompt += "\n## 文化风格参考(请将以下风格意趣融入名字寓意)\n"
        for ref in style_refs:
            prompt += f"- [{ref.label}] {ref.prompt_hint}\n"

    # 三才五格约束
    if ReferenceEnum.SANCAI in refs:
        prompt += (
            "- [三才五格] 注意用字康熙笔画, 尽量使人格、地格、总格数理为吉, 三才配置相生比和。\n"
        )

    # 补充要求与排除名单
    if state.get("other"):
        prompt += f"\n## 用户补充要求\n{state['other']}\n"
    if exclude:
        prompt += (
            f"\n## 重要: 以下名字已生成过, 本次必须完全避开, 不允许出现任何重复\n"
            f"{json.dumps(exclude, ensure_ascii=False)}\n"
        )

    prompt += f"""
## 输出要求
1. 严格生成 {count} 个候选名字(含姓的完整名字), 名字部分为 {name_length} 个字, 按综合推荐度从高到低排序。
2. 每个名字必须与姓氏组合通顺, 发音响亮, 避免不良谐音。
3. 每个名字的解释要专业简短(每项不超过30字)。
4. 严格按照以下 markdown 格式输出(不要 ``` 包裹, 不要输出其他无关内容):

## **姓名1**
五行: 
星座: 
寓意: 

## **姓名2**
五行: 
星座: 
寓意: 

...(共 {count} 个)

## 推荐总结
用1-2句话总结这批名字的整体思路与最佳推荐。
"""
    return prompt


async def generate_name_result(state: BabyNameState, config: RunnableConfig) -> dict:
    """LLM 流式生成候选名字"""
    model: BaseChatModel = config.get("configurable", {}).get("model")
    writer = get_stream_writer()
    markdown = ""
    response_stream = model.astream(_build_prompt(state))
    async for chunk in response_stream:
        if chunk.content:
            markdown += chunk.content
            writer(StreamOne(content=chunk.content, node_name="generate_name_result"))
    return {"name_markdown": markdown}


# ==================== 结果评定节点(纯程序) ====================

_NAME_PATTERN = re.compile(r"##\s*\*\*(.+?)\*\*")


def _extract_names(markdown: str, surname: str) -> list[str]:
    """从 LLM markdown 输出中解析候选名字(去重、过滤非姓名行)"""
    names: list[str] = []
    for match in _NAME_PATTERN.finditer(markdown):
        name = match.group(1).strip().replace(" ", "").replace("　", "")
        # 过滤"推荐总结"等非名字标题
        if "推荐" in name or "总结" in name or len(name) < 2 or len(name) > 4:
            continue
        # 保证含姓且未重复
        if not name.startswith(surname):
            name = surname + name.lstrip(surname)
        if name not in names:
            names.append(name)
    return names


async def finalize_result(state: BabyNameState, config: RunnableConfig) -> dict:
    """解析名字清单并程序评定三才五格, 以结构化 JSON 推送"""
    markdown = state.get("name_markdown", "")
    surname = state.get("surname", "")
    refs = state.get("references", [])
    names = _extract_names(markdown, surname)

    evaluated: list[dict] = []
    for name in names:
        item: dict = {"name": name, "meaning": "", "sancai": None, "score": 0}
        # 提取该名字下的寓意(若有)
        pattern = re.compile(rf"##\s*\*\*{re.escape(name)}\*\*\s*(.*?)(?=\n##|\Z)", re.S)
        seg = pattern.search(markdown)
        if seg:
            meaning_match = re.search(r"寓意[:：]\s*(.+)", seg.group(1))
            if meaning_match:
                item["meaning"] = meaning_match.group(1).strip()
        # 三才五格评定(选中三才参考时)
        if ReferenceEnum.SANCAI in refs and surname and len(name) > len(surname):
            result = evaluate_name(surname, name[len(surname):])
            item["sancai"] = {
                "strokes": result.strokes,
                "estimated_chars": result.estimated_chars,
                "tian_ge": result.tian_ge,
                "ren_ge": result.ren_ge,
                "di_ge": result.di_ge,
                "wai_ge": result.wai_ge,
                "zong_ge": result.zong_ge,
                "sancai": result.sancai,
                "grid_lucks": result.grid_lucks,
                "score": result.score,
            }
            item["score"] = result.score
        evaluated.append(item)

    writer = get_stream_writer()
    writer(StreamOne(content=json.dumps(evaluated, ensure_ascii=False), node_name="names_evaluated"))
    return {}


async def start(state: BabyNameState, config: RunnableConfig) -> dict:
    """启动节点"""
    return {}


def create_baby_name_graph() -> StateGraph:
    """创建宝宝起名流程图: 严格计算(并行) → LLM起名 → 程序评定"""
    workflow = StateGraph(BabyNameState)
    workflow.add_node("start", start)
    workflow.add_node("calc_wuxing", calc_wuxing)
    workflow.add_node("calc_constellation", calc_constellation)
    workflow.add_node("calc_zodiac", calc_zodiac)
    workflow.add_node("calc_tarot", calc_tarot)
    workflow.add_node("generate_name_result", generate_name_result)
    workflow.add_node("finalize_result", finalize_result)

    # 四个严格计算节点并行扇出, 汇聚后进入起名
    workflow.add_edge(START, "start")
    for node in ("calc_wuxing", "calc_constellation", "calc_zodiac", "calc_tarot"):
        workflow.add_edge("start", node)
        workflow.add_edge(node, "generate_name_result")
    workflow.add_edge("generate_name_result", "finalize_result")
    workflow.add_edge("finalize_result", END)
    return workflow


class BabyNameStreamGenerator:
    """宝宝起名流式生成器"""

    def __init__(self):
        self.graph = create_baby_name_graph().compile()

    async def generate_stream(
        self,
        name_info_predict_full: NameInfoPredictFull,
        model: BaseChatModel,
    ):
        """执行起名流程并流式输出

        :param name_info_predict_full: 宝宝信息+起名配置(BabyNameGenerateRequest 或兼容旧模型)
        :param model: LLM 模型实例
        :yield: StreamOne 流式事件
        """
        initial_state = BabyNameState(
            birth_date=name_info_predict_full.birth_date,
            birth_time=name_info_predict_full.birth_time,
            gender=str(getattr(name_info_predict_full.gender, "value", name_info_predict_full.gender)),
            surname=name_info_predict_full.surname,
            name_length=name_info_predict_full.name_length,
            other=name_info_predict_full.other,
            references=list(getattr(name_info_predict_full, "references", []) or []),
            count=getattr(name_info_predict_full, "count", 20) or 20,
            exclude_names=list(getattr(name_info_predict_full, "exclude_names", []) or []),
            calc_texts={},
            name_markdown="",
        )
        config = {"configurable": {"model": model}}
        async for chunk in self.graph.astream(
            initial_state, stream_mode="custom", config=config, version="v2"
        ):
            data: StreamOne | None = chunk.get("data")
            if data:
                yield data


# 全局单例
baby_name_generator = BabyNameStreamGenerator()
