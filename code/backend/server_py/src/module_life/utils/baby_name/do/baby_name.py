from pydantic import BaseModel, Field
from enum import Enum
from module_life.utils.baby_name.folklore import ReferenceEnum

class GenderEnum(str, Enum):
    """性别枚举"""

    BOY = "boy"
    GIRL = "girl"
    UNKNOWN = "unknown"


class NameStyleEnum(str, Enum):
    """名字风格枚举"""

    TRADITIONAL = "traditional"  # 传统
    MODERN = "modern"  # 现代
    LITERARY = "literary"  # 文艺
    SIMPLE = "simple"  # 简约
    UNIQUE = "unique"  # 独特


class NameInfoBase(BaseModel):
    """宝宝天生信息"""

    birth_date: str = Field(description="出生日期,考虑农历描述")
    birth_time: str = Field(description="出生时间，考虑时辰描述")
    gender: GenderEnum = Field(description="性别")
    surname: str = Field(description="姓")


class NameInfoEX(BaseModel):
    """宝宝额外信息"""

    name_length: int = Field(default=2, description="名字长度")
    other: str = Field(
        default="",
        description="补充信息,如首选发音、禁止字符、特殊字符、数字、风格、含义等",
    )

class NameInfoPredictFull(NameInfoBase, NameInfoEX):
    # 用于推测姓名信息的完整模型
    pass
class NameInfoPredictFullRequest(NameInfoPredictFull):
    # 推测姓名信息的完整模型
    model_id: str = Field(description="模型ID")

class NameInfoPreference(BaseModel):
    # 推测的五行星座等偏好
    wuxing_preference: list[str] = Field(
        description="五行偏好，结合name_length按顺序每个字的属性，可以多个"
    )
    constellation_preference: list[str] = Field(description="星座偏好")


class NameInfoFull(NameInfoBase, NameInfoEX, NameInfoPreference):
    # 用于推测姓名信息的完整模型
    pass


# 推测结果对象和解释
class NameInfoResultBase(BaseModel):
    # 推测结果
    name: str = Field(description="宝宝完整名字")


class NameInfoResultExplanation(BaseModel):
    # 解释
    explanation_wuxing: str = Field(description="名字的五行解释")
    explanation_constellation: str = Field(description="名字的星座解释")
    explanation_meaning: str = Field(description="名字的寓意解释")


class NameInfoResult(NameInfoResultBase, NameInfoResultExplanation):
    # 推测结果和解释
    pass


class NameInfoResultList(BaseModel):
    results: list[NameInfoResult] = Field(description="推测结果列表")


# ==================== 参考体系推算模型 ====================

class FourPillarInfo(BaseModel):
    """单柱干支信息"""

    label: str = Field(description="柱名(年柱/月柱/日柱/时柱)")
    ganzhi: str = Field(description="干支, 如 丙午")
    wuxing: str = Field(description="干支五行, 如 火火")


class WuxingInfo(BaseModel):
    """五行八字推算结果"""

    pillars: list[FourPillarInfo] = Field(description="四柱干支")
    counts: dict[str, int] = Field(description="五行个数统计 {金木水火土}")
    canggan: list[dict[str, str]] = Field(description="地支藏干明细")
    day_master: str = Field(description="日主五行")
    strength: str = Field(description="日主强弱(身强/身弱)")
    favorable: list[str] = Field(description="喜用五行(起名宜补, 按优先级)")
    summary: str = Field(description="一句话总结")


class ConstellationInfo(BaseModel):
    """星座推算结果"""

    name: str = Field(description="星座名")
    date_range: str = Field(description="日期区间")
    element: str = Field(description="四大元素(火土风水)")
    traits: str = Field(description="性格特质")
    summary: str = Field(description="一句话总结")


class ZodiacInfo(BaseModel):
    """生肖推算结果"""

    name: str = Field(description="生肖名")
    year_ganzhi: str = Field(description="年柱干支(立春分界)")
    favorable_chars: str = Field(description="传统宜用字根提示")
    summary: str = Field(description="一句话总结")


class TarotInfo(BaseModel):
    """塔罗牌推算结果"""

    number: int = Field(description="生命灵数(1-22)")
    card: str = Field(description="生命塔罗牌名")
    meaning: str = Field(description="牌意")
    summary: str = Field(description="一句话总结")


class SancaiBaseInfo(BaseModel):
    """姓氏三才五格基准(推测阶段仅姓氏可算天格基准)"""

    surname_strokes: dict[str, int] = Field(description="姓氏各字康熙笔画")
    estimated_chars: list[str] = Field(description="笔画为估计值的字")
    tian_ge: int = Field(description="天格(单姓=笔画+1, 复姓=笔画和)")
    note: str = Field(description="说明(完整五格需待名字生成后评定)")


class ReferenceCalculateRequest(NameInfoBase):
    """参考体系推算请求"""

    references: list[ReferenceEnum] = Field(
        description="要推算的参考体系列表(strict 项才参与计算)"
    )


class BuddhismInfo(BaseModel):
    """佛教本命佛推算结果(按生肖取守护佛)"""

    zodiac: str = Field(description="生肖(立春分界)")
    buddha: str = Field(description="本命佛名")
    meaning: str = Field(description="本命佛寓意")
    hint_chars: str = Field(description="佛家意趣宜用字")
    summary: str = Field(description="一句话总结")


class TaoismInfo(BaseModel):
    """道教本命太岁推算结果(按年柱干支取值年太岁)"""

    year_ganzhi: str = Field(description="年柱干支(立春分界)")
    taishi: str = Field(description="本命太岁星君")
    meaning: str = Field(description="太岁文化寓意")
    hint_chars: str = Field(description="道家意趣宜用字")
    summary: str = Field(description="一句话总结")


class ChristianInfo(BaseModel):
    """基督圣经意象推算结果(按出生季节取主题经文)"""

    season: str = Field(description="出生季节(春夏秋冬)")
    theme: str = Field(description="圣经主题意象")
    verse: str = Field(description="对应经文(含出处)")
    hint_chars: str = Field(description="祝福意趣宜用字")
    summary: str = Field(description="一句话总结")


class ReferenceCalculateResult(BaseModel):
    """参考体系推算结果(按选择返回对应子对象, 未选为 None)"""

    wuxing: WuxingInfo | None = Field(None, description="五行八字结果")
    constellation: ConstellationInfo | None = Field(None, description="星座结果")
    zodiac: ZodiacInfo | None = Field(None, description="生肖结果")
    tarot: TarotInfo | None = Field(None, description="塔罗牌结果")
    sancai: SancaiBaseInfo | None = Field(None, description="姓氏五格基准结果")
    buddhism: BuddhismInfo | None = Field(None, description="佛教本命佛结果")
    taoism: TaoismInfo | None = Field(None, description="道教本命太岁结果")
    christian: ChristianInfo | None = Field(None, description="基督圣经意象结果")


class SancaiScore(BaseModel):
    """单个名字的三才五格评分"""

    strokes: list[int] = Field(description="每个字康熙笔画(姓+名)")
    estimated_chars: list[str] = Field(description="笔画为估计值的字")
    tian_ge: int = Field(description="天格")
    ren_ge: int = Field(description="人格")
    di_ge: int = Field(description="地格")
    wai_ge: int = Field(description="外格")
    zong_ge: int = Field(description="总格")
    sancai: str = Field(description="三才配置, 如 木火土")
    grid_lucks: dict[str, str] = Field(description="各格吉凶")
    score: int = Field(description="评分 0-100")


class EvaluatedName(BaseModel):
    """生成后经程序评定的名字"""

    name: str = Field(description="宝宝完整名字(含姓)")
    meaning: str = Field(default="", description="名字寓意(从生成文本提取)")
    sancai: SancaiScore | None = Field(None, description="三才五格评定(选择三才参考时)")
    score: int = Field(default=0, description="综合评分 0-100")


class BabyNameGenerateRequest(NameInfoPredictFullRequest):
    """起名生成请求(流式)"""

    # 覆盖父类必填约束: 起名支持不选模型, 留空自动使用默认公共 chat 模型
    model_id: str = Field(default="", description="模型ID(留空自动使用默认公共 chat 模型)")
    references: list[ReferenceEnum] = Field(
        default_factory=list, description="参考的民俗/神话体系(多选)"
    )
    count: int = Field(default=20, ge=1, le=50, description="本次生成名字数量")
    exclude_names: list[str] = Field(
        default_factory=list, description="需避开的历史名字(生成更多时传已生成名单防重复)"
    )
