"""起名参考体系注册表

两类参考:
- strict=True: 有经典严格计算方法, 由后端程序精确推算(五行八字/三才五格/星座/生肖/塔罗);
- strict=False: 文化风格类参考(基督/佛教/道教), 无量化计算, 转化为起名风格约束注入提示词。
"""

from dataclasses import dataclass
from enum import StrEnum


class ReferenceEnum(StrEnum):
    """参考体系标识(与前端多选卡片一一对应)"""

    WUXING = "wuxing"  # 五行八字
    SANCAI = "sancai"  # 三才五格
    CONSTELLATION = "constellation"  # 星座
    ZODIAC = "zodiac"  # 生肖
    TAROT = "tarot"  # 塔罗牌
    CHRISTIAN = "christian"  # 基督
    BUDDHISM = "buddhism"  # 佛教
    TAOISM = "taoism"  # 道教


@dataclass(frozen=True)
class FolkReference:
    """单个参考体系定义"""

    key: str
    label: str
    icon: str  # 前端展示图标(emoji)
    desc: str  # 一句话说明
    strict: bool  # 是否有严格程序化计算
    prompt_hint: str  # 注入起名提示词的风格约束


FOLK_REFERENCES: dict[str, FolkReference] = {
    ReferenceEnum.WUXING: FolkReference(
        key=ReferenceEnum.WUXING,
        label="五行八字",
        icon="☯",
        desc="生辰干支四柱推算五行强弱与喜用神",
        strict=True,
        prompt_hint="优先选用补益喜用五行的字(偏旁、部首或字义属性行相符), 名字五行与八字喜用呼应",
    ),
    ReferenceEnum.SANCAI: FolkReference(
        key=ReferenceEnum.SANCAI,
        label="三才五格",
        icon="☰",
        desc="康熙笔画五格数理与天人地三才配置",
        strict=True,
        prompt_hint="兼顾五格数理为吉(人格/地格/总格尤重), 三才配置尽量相生比和",
    ),
    ReferenceEnum.CONSTELLATION: FolkReference(
        key=ReferenceEnum.CONSTELLATION,
        label="星座",
        icon="✦",
        desc="公历日期严格划分十二星座与性格意象",
        strict=True,
        prompt_hint="用字气质与星座性格特质呼应",
    ),
    ReferenceEnum.ZODIAC: FolkReference(
        key=ReferenceEnum.ZODIAC,
        label="生肖",
        icon="🧧",
        desc="按立春分界推算生肖与宜用字形",
        strict=True,
        prompt_hint="结合生肖宜用字根(如艹、月、禾等传统喜忌)择字",
    ),
    ReferenceEnum.TAROT: FolkReference(
        key=ReferenceEnum.TAROT,
        label="塔罗牌",
        icon="🃏",
        desc="生命灵数推算生命塔罗牌寓意",
        strict=True,
        prompt_hint="名字寓意与生命塔罗牌的精神内核相合",
    ),
    ReferenceEnum.CHRISTIAN: FolkReference(
        key=ReferenceEnum.CHRISTIAN,
        label="基督",
        icon="✝",
        desc="圣经美好品德与恩典意象",
        strict=False,
        prompt_hint="可参考圣经中的美好品德与意象(恩典、光、平安、喜乐), 寓意温和祝福",
    ),
    ReferenceEnum.BUDDHISM: FolkReference(
        key=ReferenceEnum.BUDDHISM,
        label="佛教",
        icon="☸",
        desc="慈悲智慧清净的禅意用字",
        strict=False,
        prompt_hint="可参考佛教慈悲、智慧、清净的意象(如慧、净、慈、莲、安), 气质禅意祥和",
    ),
    ReferenceEnum.TAOISM: FolkReference(
        key=ReferenceEnum.TAOISM,
        label="道教",
        icon="☯",
        desc="道法自然清静逍遥的道家意趣",
        strict=False,
        prompt_hint="可参考道家自然无为、清静逍遥的意趣(如清、然、朴、云、鹤), 气质空灵飘逸",
    ),
}


def get_reference_catalog() -> list[dict]:
    """参考体系目录(供前端多选卡片渲染)"""
    return [
        {
            "key": ref.key,
            "label": ref.label,
            "icon": ref.icon,
            "desc": ref.desc,
            "strict": ref.strict,
        }
        for ref in FOLK_REFERENCES.values()
    ]
