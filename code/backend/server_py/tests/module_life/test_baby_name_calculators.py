# -*- coding: utf-8 -*-
"""baby_name 经典算法单元测试(纯计算, 零外部依赖)

覆盖: 干支四柱(双锚点互证)、五行喜用、星座严格划分、生命塔罗牌、
康熙笔画、三才五格、参考体系目录。
"""

import datetime as dt

from module_life.utils.baby_name.almanac import (
    GAN,
    ZHI,
    ZODIAC,
    day_ganzhi_index,
    get_four_pillars,
    get_zodiac,
    hour_pillar,
    month_pillar,
    year_pillar,
)
from module_life.utils.baby_name.constellation import get_constellation
from module_life.utils.baby_name.folklore import FOLK_REFERENCES, ReferenceEnum
from module_life.utils.baby_name.sancai import evaluate_name
from module_life.utils.baby_name.strokes import stroke_of
from module_life.utils.baby_name.tarot import get_tarot, life_number
from module_life.utils.baby_name.wuxing import analyze_wuxing


# ==================== 干支四柱 ====================

def test_day_ganzhi_anchors():
    """日柱双锚点互证: 1900-01-01=甲戌(序10), 1949-10-01=甲子(序0)"""
    assert day_ganzhi_index(dt.date(1900, 1, 1)) == 10
    assert day_ganzhi_index(dt.date(1949, 10, 1)) == 0
    assert day_ganzhi_index(dt.date(1949, 10, 1)) == (day_ganzhi_index(dt.date(1900, 1, 1)) + 50) % 60


def test_day_ganzhi_known_date():
    """2026-09-13 日柱应为 庚寅(序26), 次日辛卯(序27); 已由三锚点(1900甲戌/1949甲子/2000戊午)互证"""
    idx = day_ganzhi_index(dt.date(2026, 9, 13))
    assert GAN[idx % 10] + ZHI[idx % 12] == "庚寅"
    idx2 = day_ganzhi_index(dt.date(2026, 9, 14))
    assert GAN[idx2 % 10] + ZHI[idx2 % 12] == "辛卯"


def test_year_pillar_lichun_boundary():
    """年柱以立春为界: 2026-09-13→丙午; 2026-01-01(立春前)→乙巳; 1984-05-01→甲子"""
    assert GAN[year_pillar(dt.date(2026, 9, 13))[0]] + ZHI[year_pillar(dt.date(2026, 9, 13))[1]] == "丙午"
    assert GAN[year_pillar(dt.date(2026, 1, 1))[0]] + ZHI[year_pillar(dt.date(2026, 1, 1))[1]] == "乙巳"
    assert GAN[year_pillar(dt.date(1984, 5, 1))[0]] + ZHI[year_pillar(dt.date(1984, 5, 1))[1]] == "甲子"


def test_month_pillar_wuhudun():
    """月柱: 2026-09-13(白露后)→丁酉月(丙午年五虎遁庚寅起); 立春后寅月=庚寅"""
    gan, zhi = month_pillar(dt.date(2026, 9, 13))
    assert GAN[gan] + ZHI[zhi] == "丁酉"
    gan, zhi = month_pillar(dt.date(2026, 2, 10))
    assert GAN[gan] + ZHI[zhi] == "庚寅"


def test_hour_pillar_wushudun():
    """时柱五鼠遁: 庚日(2026-09-13)08:00→辰时, 丙子起→庚辰时"""
    gan, zhi = hour_pillar(dt.date(2026, 9, 13), 8)
    assert GAN[gan] + ZHI[zhi] == "庚辰"


def test_hour_pillar_late_zishi():
    """晚子时(23点后)归次日: 2026-09-13 23:30 → 次日辛卯日, 时干按次日辛日五鼠遁(丙辛起戊子)→戊子"""
    gan, zhi = hour_pillar(dt.date(2026, 9, 13), 23)
    assert ZHI[zhi] == "子"
    assert GAN[gan] == "戊"


def test_four_pillars_names():
    """2026-09-13 08:00 四柱: 丙午 丁酉 庚寅 庚辰"""
    names = get_four_pillars("2026-09-13", "08:00").names()
    assert names == ["丙午", "丁酉", "庚寅", "庚辰"]


def test_zodiac_lichun_boundary():
    """生肖按立春分界: 2026-09-13→马(午); 2026-01-01→蛇(巳)"""
    assert get_zodiac("2026-09-13") == ZODIAC[6] == "马"
    assert get_zodiac("2026-01-01") == "蛇"


def test_solar_term_time_anchors():
    """节气天文解锚点(寿星通式曾出错的年份, 日期以紫金山天文台历表为准):
    2022/2026 立春=2/4(通式误算2/3), 2024 小寒=1/6(通式误算1/5), 其余抽检"""
    from module_life.utils.baby_name.almanac import _solar_term_time

    anchors = {
        ("立春", 2022): (2, 4), ("立春", 2024): (2, 4),
        ("立春", 2025): (2, 3), ("立春", 2026): (2, 4),
        ("小寒", 2021): (1, 5), ("小寒", 2024): (1, 6),
        ("小寒", 2026): (1, 5), ("大寒", 2024): (1, 20),
        ("冬至", 2025): (12, 21), ("白露", 2026): (9, 7),
    }
    for (term, year), (m, d) in anchors.items():
        t = _solar_term_time(year, term)
        assert (t.month, t.day) == (m, d), f"{year}{term} 应为 {m}/{d}, 实得 {t}"


def test_year_pillar_lichun_day_boundary():
    """立春当日年柱按时刻分界: 2026-02-04 04:02 立春, 03点仍乙巳年、06点起丙午年;
    前一日(2/3)整日属乙巳年"""
    assert year_pillar(dt.date(2026, 2, 4), 3) == year_pillar(dt.date(2026, 2, 3))
    assert year_pillar(dt.date(2026, 2, 4), 6) == year_pillar(dt.date(2026, 2, 10))


def test_month_pillar_xiaohan_boundary():
    """小寒分界回归(2024 小寒=1/6 04:49, 通式曾误算 1/5):
    1/5→上一年癸卯年甲子月, 1/6→癸卯年乙丑月(年柱仍以立春分界)"""
    y = year_pillar(dt.date(2024, 1, 5))
    assert GAN[y[0]] + ZHI[y[1]] == "癸卯"
    gan, zhi = month_pillar(dt.date(2024, 1, 5))
    assert GAN[gan] + ZHI[zhi] == "甲子"
    gan, zhi = month_pillar(dt.date(2024, 1, 6))
    assert GAN[gan] + ZHI[zhi] == "乙丑"


def test_month_pillar_time_boundary():
    """月柱按节气时刻分界: 2026 白露=9/7 22:41, 当日 20点仍申月(丙申)、23点起酉月(丁酉)"""
    gan, zhi = month_pillar(dt.date(2026, 9, 7), 20)
    assert GAN[gan] + ZHI[zhi] == "丙申"
    gan, zhi = month_pillar(dt.date(2026, 9, 7), 23)
    assert GAN[gan] + ZHI[zhi] == "丁酉"


def test_four_pillars_late_zi_day_carry():
    """晚子时日柱同步进位: 2026-09-13(庚寅日)23:30 → 日柱辛卯、时柱戊子;
    22:30(亥时)不进位 → 庚寅/丁亥"""
    assert get_four_pillars("2026-09-13", "23:30").names() == ["丙午", "丁酉", "辛卯", "戊子"]
    assert get_four_pillars("2026-09-13", "22:30").names() == ["丙午", "丁酉", "庚寅", "丁亥"]


# ==================== 五行喜用 ====================

def test_analyze_wuxing_counts_and_favorable():
    """2026-09-13 08:00 八字 丙午丁酉庚寅庚辰: 金3火3土1木1缺水, 日主庚金,
    同类=金3+印土1=4, 异类=木1水0火3=4, 4<4为假 → 身强, 喜克泄耗按少者先(水木火), 缺水优先"""
    result = analyze_wuxing("2026-09-13", "08:00")
    assert result["pillar_names"] == ["丙午", "丁酉", "庚寅", "庚辰"]
    assert result["counts"] == {"金": 3, "木": 1, "水": 0, "火": 3, "土": 1}
    assert result["day_master"] == "金"
    assert result["strength"] == "身强"
    # 缺失的水必须排最前, 其次数量最少的财星木
    assert result["favorable"][:2] == ["水", "木"]


def test_analyze_wuxing_day_master_label():
    """日主取日柱天干五行: 2026-02-10 12:00 日柱天干应可识别"""
    result = analyze_wuxing("2026-02-10", "12:00")
    assert result["day_master"] in {"金", "木", "水", "火", "土"}
    assert len(result["pillar_names"]) == 4


# ==================== 星座 ====================

def test_constellation_strict_boundaries():
    """星座严格边界: 9/13处女座, 3/21白羊座, 3/20双鱼座, 1/5与12/25摩羯座"""
    assert get_constellation("2026-09-13").name == "处女座"
    assert get_constellation("2026-03-21").name == "白羊座"
    assert get_constellation("2026-03-20").name == "双鱼座"
    assert get_constellation("2026-01-05").name == "摩羯座"
    assert get_constellation("2026-12-25").name == "摩羯座"


def test_constellation_elements():
    """元素象限: 白羊属火, 金牛属土, 双子属风, 巨蟹属水"""
    assert get_constellation("2026-04-05").element == "火"
    assert get_constellation("2026-05-01").element == "土"
    assert get_constellation("2026-06-01").element == "风"
    assert get_constellation("2026-07-01").element == "水"


# ==================== 塔罗牌 ====================

def test_tarot_life_number():
    """生命灵数: 2026-09-13 → 2+0+2+6+9+1+3=23 → 5; 2000-01-01 → 4"""
    assert life_number("2026-09-13") == 5
    assert life_number("2000-01-01") == 4


def test_tarot_card_mapping():
    """灵数5→教皇; 1999-12-31: 1+9+9+9+1+2+3+1=35 → 8 力量"""
    assert get_tarot("2026-09-13")["card"] == "教皇"
    assert get_tarot("1999-12-31")["card"] == "力量"


# ==================== 康熙笔画与三才五格 ====================

def test_strokes_anchors():
    """康熙笔画锚点: 王4 李7 张11 刘15 陈16 雨8 涵12 明8 轩10"""
    for char, n in {"王": 4, "李": 7, "张": 11, "刘": 15, "陈": 16, "雨": 8, "涵": 12, "明": 8, "轩": 10}.items():
        strokes, exact = stroke_of(char)
        assert (strokes, exact) == (n, True), f"{char} 应为 {n} 画"


def test_strokes_fallback_estimated():
    """未收录字回退简体字数并标记估计值"""
    strokes, exact = stroke_of("仧")
    assert exact is False
    assert strokes == 1


def test_sancai_wang_yu_han():
    """王雨涵: 王4雨8涵12 → 天5吉 人12凶 地20凶 外13吉 总24吉, 三才土木水"""
    r = evaluate_name("王", "雨涵")
    assert r.strokes == [4, 8, 12]
    assert (r.tian_ge, r.ren_ge, r.di_ge, r.wai_ge, r.zong_ge) == (5, 12, 20, 13, 24)
    assert r.sancai == "土木水"
    assert r.grid_lucks == {"天格": "吉", "人格": "凶", "地格": "凶", "外格": "吉", "总格": "吉"}
    assert 0 <= r.score <= 100


def test_sancai_single_char_name():
    """单姓单名: 李明 → 天8 人15 地9 外2 总15"""
    r = evaluate_name("李", "明")
    assert r.strokes == [7, 8]
    assert (r.tian_ge, r.ren_ge, r.di_ge, r.wai_ge, r.zong_ge) == (8, 15, 9, 2, 15)


def test_sancai_compound_surname():
    """复姓单名: 司马光(司5马10光6) → 天15(复姓=笔画和) 人16 地7 外6 总21"""
    r = evaluate_name("司马", "光")
    assert r.strokes == [5, 10, 6]
    assert (r.tian_ge, r.ren_ge, r.di_ge, r.wai_ge, r.zong_ge) == (15, 16, 7, 6, 21)


# ==================== 参考体系目录 ====================

def test_reference_catalog():
    """目录含 8 个参考体系, 严格计算项与风格类标记正确"""
    assert set(FOLK_REFERENCES.keys()) == {e for e in ReferenceEnum}
    strict_keys = {k for k, v in FOLK_REFERENCES.items() if v.strict}
    assert strict_keys == {"wuxing", "sancai", "constellation", "zodiac", "tarot"}
    style_keys = {k for k, v in FOLK_REFERENCES.items() if not v.strict}
    assert style_keys == {"christian", "buddhism", "taoism"}
