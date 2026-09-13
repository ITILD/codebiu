"""历法干支模块：节气近似、四柱八字(年/月/日/时干支)、生肖

经典算法说明:
- 日柱: 以儒略日数(JDN)为基准, 甲子日满足 (JDN - 11) % 60 == 0。
  双锚点互证: 1900-01-01 为甲戌日(序10)、1949-10-01 为甲子日(序0)。
- 年柱: 以立春为界, 立春前属前一年 (子平术正统分界)。
- 月柱: 以十二"节"(立春/惊蛰/清明/立夏/芒种/小暑/立秋/白露/寒露/立冬/大雪/小寒)分界,
  月干由年干五虎遁得出。
- 时柱: 十二时辰按小时分界, 时干由日干五鼠遁得出;
  23:00 后按主流子平惯例归入次日子时(日柱进一天)。
- 节气日期: 采用"寿星通式" [Y*D + C] - L (D=0.2422, 1/2月节气按上一年取 Y),
  绝大多数年份精确到日, 个别年份可能偏差 1 天(分界日出生者建议核对当年精确节气时刻)。
"""

from dataclasses import dataclass
import datetime as dt

# 天干地支及五行
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WUXING = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"]
ZHI_WUXING = ["水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水"]
# 地支藏干(主气在前): 用于精细五行统计
ZHI_CANGGAN = [
    "癸", "己癸辛", "甲丙戊", "乙", "戊乙癸", "丙庚戊",
    "丁己", "己丁乙", "庚壬戊", "辛", "戊辛丁", "壬甲",
]
GAN_WUXING_MAP = dict(zip(GAN, GAN_WUXING))
ZHI_WUXING_MAP = dict(zip(ZHI, ZHI_WUXING))

# 生肖(按年支)
ZODIAC = "鼠牛虎兔龙蛇马羊猴鸡狗猪"

# 寿星通式 24 节气 C 值(21世纪)
_SOLAR_TERM_C_21 = {
    "小寒": 5.4055, "大寒": 20.12, "立春": 3.87, "雨水": 18.73,
    "惊蛰": 5.63, "春分": 20.646, "清明": 4.81, "谷雨": 20.1,
    "立夏": 5.52, "小满": 21.04, "芒种": 5.678, "夏至": 21.37,
    "小暑": 7.108, "大暑": 22.83, "立秋": 7.5, "处暑": 23.13,
    "白露": 7.646, "秋分": 23.042, "寒露": 8.318, "霜降": 23.438,
    "立冬": 7.438, "小雪": 22.36, "大雪": 7.18, "冬至": 21.94,
}
# 寿星通式 24 节气 C 值(20世纪, 2000年前出生)
_SOLAR_TERM_C_20 = {
    "小寒": 6.11, "大寒": 20.84, "立春": 4.6295, "雨水": 19.4599,
    "惊蛰": 6.3826, "春分": 21.4155, "清明": 5.59, "谷雨": 20.888,
    "立夏": 6.318, "小满": 21.86, "芒种": 6.5, "夏至": 22.2,
    "小暑": 7.928, "大暑": 23.65, "立秋": 8.35, "处暑": 23.95,
    "白露": 8.44, "秋分": 23.822, "寒露": 9.098, "霜降": 24.218,
    "立冬": 8.218, "小雪": 23.08, "大雪": 7.9, "冬至": 22.6,
}

# 十二"节"(月柱分界): 节气名 -> 月支序(寅=2 对应正月)
_JIE_ORDER = [
    ("立春", 2), ("惊蛰", 3), ("清明", 4), ("立夏", 5), ("芒种", 6), ("小暑", 7),
    ("立秋", 8), ("白露", 9), ("寒露", 10), ("立冬", 11), ("大雪", 12), ("小寒", 1),
]
# 月支: 寅月起正月, 月支序号(地支索引) = 2 + 节序 (mod 12)
_JIE_MONTH_ZHI = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1]


def _jdn(date: dt.date) -> int:
    """公历日期 → 儒略日数 JDN(标准 Gregorian 公式)"""
    a = (14 - date.month) // 12
    y = date.year + 4800 - a
    m = date.month + 12 * a - 3
    return date.day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _solar_term_day(year: int, term: str) -> int:
    """寿星通式计算某年某节气的"日"(只关心几号, 精度到日)

    规则: 1/2 月节气(小寒/大寒/立春/雨水) Y 取上一年后两位, 其余取本年;
    L = Y // 4; 个别年份存在 ±1 天固有偏差(见模块注释)。
    """
    ref_year = year - 1 if term in ("小寒", "大寒", "立春", "雨水") else year
    y = ref_year % 100
    table = _SOLAR_TERM_C_21 if year >= 2000 else _SOLAR_TERM_C_20
    day = int(y * 0.2422 + table[term] - y // 4)
    return day


def day_ganzhi_index(date: dt.date) -> int:
    """日柱干支序号(0=甲子 ... 59=癸亥)"""
    return (_jdn(date) - 11) % 60


def year_pillar(date: dt.date) -> tuple[int, int]:
    """年柱 (干序, 支序): 以立春为界, 立春前属前一年"""
    year = date.year
    if date.month == 1 or (date.month == 2 and date.day < _solar_term_day(year, "立春")):
        year -= 1
    idx = (year - 4) % 60
    return idx % 10, idx % 12


def month_pillar(date: dt.date) -> tuple[int, int]:
    """月柱 (干序, 支序): 十二节分界 + 五虎遁取月干"""
    year = date.year
    # 依次判断日期落在哪个节之后(从小寒倒序到大雪)
    zhi_idx: int
    if date.month == 1 and date.day < _solar_term_day(year, "小寒"):
        # 小寒之前(1月上旬)属于上一年的子月(大雪之后)
        zhi_idx = 0
        eff_year = year - 1
    else:
        eff_year = year
        zhi_idx = 1  # 默认丑月(小寒~立春)
        # 从后往前找: 大雪(12月)→子, 立冬(11月)→亥, ...
        for i in range(len(_JIE_ORDER) - 2, -1, -1):
            term, month = _JIE_ORDER[i]
            if date.month > month or (date.month == month and date.day >= _solar_term_day(year, term)):
                zhi_idx = _JIE_MONTH_ZHI[i]
                break
    # 五虎遁: 年干甲己→丙寅起, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅
    year_gan = year_pillar(date)[0]
    first_gan = (2 * (year_gan % 5) + 2) % 10
    # 月支相对寅的偏移
    offset = (zhi_idx - 2) % 12
    return (first_gan + offset) % 10, zhi_idx


def hour_zhi_index(hour: int) -> int:
    """时支序号: 23/0→子, 1-2→丑, ... 21-22→亥"""
    return ((hour + 1) // 2) % 12


def day_pillar_for_hour(date: dt.date, hour: int) -> int:
    """考虑晚子时(23点后归次日)的日柱干支序号"""
    idx = day_ganzhi_index(date)
    if hour >= 23:
        idx = (idx + 1) % 60
    return idx


def hour_pillar(date: dt.date, hour: int) -> tuple[int, int]:
    """时柱 (干序, 支序): 五鼠遁取时干"""
    zhi = hour_zhi_index(hour)
    day_gan = day_pillar_for_hour(date, hour) % 10
    # 五鼠遁: 日干甲己→甲子起, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子
    first_gan = (2 * (day_gan % 5)) % 10
    return (first_gan + zhi) % 10, zhi


@dataclass
class FourPillars:
    """四柱八字: 每柱为 (干序, 支序)"""

    year: tuple[int, int]
    month: tuple[int, int]
    day: tuple[int, int]
    hour: tuple[int, int]

    @staticmethod
    def _name(pillar: tuple[int, int]) -> str:
        return GAN[pillar[0]] + ZHI[pillar[1]]

    def names(self) -> list[str]:
        """四柱干支名, 如 ["丙午","丁酉","庚辰","戊辰"]"""
        return [self._name(p) for p in (self.year, self.month, self.day, self.hour)]

    def labels(self) -> list[str]:
        return ["年柱", "月柱", "日柱", "时柱"]


def get_four_pillars(birth_date: str, birth_time: str) -> FourPillars:
    """由出生日期(YYYY-MM-DD)与时间(HH:mm)推算四柱八字

    :param birth_date: 公历出生日期
    :param birth_time: 出生时间(24小时制)
    :return: FourPillars 四柱
    """
    d = dt.date.fromisoformat(birth_date)
    try:
        h, m = birth_time.split(":")
        hour = int(h)
    except ValueError:
        hour = 12  # 未提供精确时间时按午时兜底
    return FourPillars(
        year=year_pillar(d),
        month=month_pillar(d),
        day=(day_ganzhi_index(d) % 10, day_ganzhi_index(d) % 12),
        hour=hour_pillar(d, hour),
    )


def get_zodiac(birth_date: str) -> str:
    """按年柱地支取生肖(立春分界)"""
    return ZODIAC[year_pillar(dt.date.fromisoformat(birth_date))[1]]


# 生肖传统宜用字根(起名民俗参考)
ZODIAC_HINTS: dict[str, str] = {
    "鼠": "宜用宀、米、豆、金、玉等字根; 慎用日、火、人字根",
    "牛": "宜用艹、田、禾、金、谷等字根; 慎用马、山字根",
    "虎": "宜用山、林、木、王、君等字根; 慎用日、蛇形字根",
    "兔": "宜用艹、月、禾、口、木等字根; 慎用日、心、辰龙字根",
    "龙": "宜用氵、云、雨、日、月、王等字根; 慎用犬、田字根",
    "蛇": "宜用口、木、田、山、鱼等字根; 慎用氵、亥猪字根",
    "马": "宜用艹、木、禾、龙、寅虎等字根; 慎用子、牛、山字根",
    "羊": "宜用艹、木、豆、米、几等字根; 慎用丑牛、心字根",
    "猴": "宜用木、水、亻、王、子等字根; 慎用寅虎、亥猪字根",
    "鸡": "宜用米、豆、山、艹、金等字根; 慎用卯兔、犬字根",
    "狗": "宜用亻、入、艹、金、玉等字根; 慎用鸡形、田字根",
    "猪": "宜用宀、米、豆、金、木等字根; 慎用示(祭祀)、蛇形字根",
}
