"""星座计算: 按公历出生日期严格划分十二星座(占星学标准分界日期)

分界日期为占星学通用的太阳黄经分界(每年因岁差仅浮动 1 天内, 采用固定区间标准)。
"""

from dataclasses import dataclass
import datetime as dt

# 星座: (名称, 起始月-日, 元素, 特质摘要)
CONSTELLATIONS: list[tuple[str, tuple[int, int], str, str]] = [
    ("白羊座", (3, 21), "火", "热情勇敢、行动力强、率真坦荡"),
    ("金牛座", (4, 20), "土", "稳重务实、坚毅耐心、重视美感"),
    ("双子座", (5, 21), "风", "聪敏好奇、善于沟通、灵活多变"),
    ("巨蟹座", (6, 22), "水", "温柔体贴、顾家念旧、情感细腻"),
    ("狮子座", (7, 23), "火", "自信大方、有领导力、光明磊落"),
    ("处女座", (8, 23), "土", "细致严谨、追求完美、乐于服务"),
    ("天秤座", (9, 23), "风", "优雅和善、崇尚公正、擅长协调"),
    ("天蝎座", (10, 23), "水", "深沉专注、意志坚定、洞察力强"),
    ("射手座", (11, 22), "火", "乐观自由、热爱探索、率性洒脱"),
    ("摩羯座", (12, 22), "土", "踏实自律、目标坚定、厚积薄发"),
    ("水瓶座", (1, 20), "风", "独立创新、思想超前、博爱友善"),
    ("双鱼座", (2, 19), "水", "浪漫柔情、富有想象、慈悲善良"),
]


@dataclass
class ConstellationInfo:
    """星座信息"""

    name: str  # 星座名
    date_range: str  # 日期区间描述
    element: str  # 四大元素(火土风水)
    traits: str  # 性格特质

    def summary(self) -> str:
        return f"星座: {self.name}({self.date_range}), 属{self.element}象星座。特质: {self.traits}"


def _date_key(month: int, day: int) -> int:
    """月日 → 可比较键"""
    return month * 100 + day


def get_constellation(birth_date: str) -> ConstellationInfo:
    """按公历日期严格划分星座

    :param birth_date: 公历出生日期(YYYY-MM-DD)
    :return: ConstellationInfo
    """
    d = dt.date.fromisoformat(birth_date)
    key = _date_key(d.month, d.day)
    # 各星座起始边界(当前星座名对应起点, 水瓶座起 1/20 环形判断)
    for i, (name, start, element, traits) in enumerate(CONSTELLATIONS):
        next_start = CONSTELLATIONS[(i + 1) % 12][1]
        s_key, n_key = _date_key(*start), _date_key(*next_start)
        if s_key <= key < n_key:
            return ConstellationInfo(
                name=name,
                date_range=f"{start[0]}月{start[1]}日-{next_start[0]}月{next_start[1] - 1}日",
                element=element,
                traits=traits,
            )
    # 12/22 以后到次年 1/19 之间属于摩羯座(环形区间兜底)
    name, start, element, traits = CONSTELLATIONS[9]
    return ConstellationInfo(
        name=name,
        date_range=f"12月22日-1月19日",
        element=element,
        traits=traits,
    )
