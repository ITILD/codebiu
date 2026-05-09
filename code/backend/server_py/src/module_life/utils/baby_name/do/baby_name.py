from pydantic import BaseModel, Field
from enum import Enum

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
        description="补充信息,如首选发音、禁止字符、特殊字符、数字、风格、含义等"
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
