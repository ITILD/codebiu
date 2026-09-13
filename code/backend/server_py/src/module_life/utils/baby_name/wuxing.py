"""五行八字分析: 天干地支五行统计、日主强弱、喜用神(经典简化规则)

喜用神判定采用经典"扶抑法"简化版:
- 统计八字(天干4 + 地支主气4)五行个数;
- 同类 = 日主五行 + 生日主的五行(印); 异类 = 克/泄/耗日主的五行;
- 同类弱于异类 → 身弱, 喜生扶(印星/比劫); 反之身强, 喜克泄耗(官杀/食伤/财星);
- 五行有缺(数量为0)优先补缺。
注: 严格喜用神还需结合月令旺衰与刑冲合害, 此处为通用的扶抑近似, 供起名参考。
"""

from module_life.utils.baby_name.almanac import (
    FourPillars,
    GAN_WUXING,
    ZHI,
    ZHI_CANGGAN,
    ZHI_WUXING,
    get_four_pillars,
)

WUXING_ORDER = ["金", "木", "水", "火", "土"]
# 五行相生: A → B
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
# 五行相克: A 克 B
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def count_wuxing(pillars: FourPillars) -> dict[str, int]:
    """统计八字五行个数(天干4 + 地支主气4), 并附地支藏干明细"""
    counts = dict.fromkeys(WUXING_ORDER, 0)
    pairs = [pillars.year, pillars.month, pillars.day, pillars.hour]
    for i, (gan, zhi) in enumerate(pairs):
        counts[GAN_WUXING[gan]] += 1
        counts[ZHI_WUXING[zhi]] += 1
    return counts


def canggan_detail(pillars: FourPillars) -> list[dict[str, str]]:
    """地支藏干明细(供专业展示): [{branch, hidden, wuxing}]"""
    pairs = [pillars.year, pillars.month, pillars.day, pillars.hour]
    return [
        {
            "pillar": pillars.labels()[i],
            "branch": ZHI[p[1]],
            "hidden": ZHI_CANGGAN[p[1]],
        }
        for i, p in enumerate(pairs)
    ]


def analyze_wuxing(birth_date: str, birth_time: str) -> dict:
    """完整五行八字分析

    :return: dict(pillars/names, counts, canggan, day_master, strength, favorable, summary)
    """
    pillars = get_four_pillars(birth_date, birth_time)
    counts = count_wuxing(pillars)
    day_gan = pillars.day[0]
    day_master = GAN_WUXING[day_gan]
    # 同类: 日主 + 生日主(印); 异类: 其余
    yin = next(w for w in WUXING_ORDER if SHENG[w] == day_master)  # 印星: 生日主者
    same = counts[day_master] + counts[yin]
    opposite = sum(v for k, v in counts.items() if k not in (day_master, yin))
    strength = "身弱" if same < opposite else "身强"

    favorable: list[str] = []
    # 缺失的五行优先补
    missing = [w for w in WUXING_ORDER if counts[w] == 0]
    favorable.extend(missing)
    if strength == "身弱":
        # 身弱喜生扶: 印星(生日主)与比劫(同日主)
        for w in (yin, day_master):
            if w not in favorable:
                favorable.append(w)
    else:
        # 身强喜克泄耗: 官杀(克日主)、食伤(日主生)、财星(日主克), 按八字中数量少者优先
        guan = next(w for w in WUXING_ORDER if KE[w] == day_master)  # 官杀: 克日主者
        shi = SHENG[day_master]  # 食伤: 日主所生
        cai = KE[day_master]  # 财星: 日主所克
        drains = [guan, shi, cai]
        drains.sort(key=lambda w: counts[w])
        for w in drains:
            if w not in favorable:
                favorable.append(w)

    summary = (
        f"八字五行: {'、'.join(f'{k}{v}' for k, v in counts.items())}; "
        f"日主{day_master}{strength}, "
        + (f"五行缺{'、'.join(missing)}。" if missing else "五行不缺。")
        + f"起名宜补{'、'.join(favorable[:2])}属性行。"
    )
    return {
        "pillar_names": pillars.names(),
        "pillar_labels": pillars.labels(),
        "counts": counts,
        "canggan": canggan_detail(pillars),
        "day_master": day_master,
        "strength": strength,
        "favorable": favorable,
        "summary": summary,
    }
