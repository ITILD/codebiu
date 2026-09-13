"""三才五格计算(姓名学经典算法)

五格剖象法:
- 天格: 单姓 = 姓氏笔画 + 1; 复姓 = 姓氏各字笔画之和
- 人格: 姓氏末字笔画 + 名字首字笔画
- 地格: 名字笔画之和(单名 + 1)
- 外格: 总格 - 人格 + 1(单姓单名固定为 2)
- 总格: 姓名全部笔画之和
数理吉凶按 81 数理表(超 81 取模)。三才 = 天/人/地格个位数的五行配置,
按生克关系评分(相生比和为吉, 相克为凶)。
"""

from dataclasses import dataclass, field

from module_life.utils.baby_name.strokes import stroke_of

# 81 数理吉凶表(主流版本)
LUCKY_NUMBERS = {
    1, 3, 5, 6, 7, 8, 11, 13, 15, 16, 17, 18, 21, 23, 24, 25, 29, 31, 32,
    33, 35, 37, 39, 41, 45, 47, 48, 52, 57, 61, 63, 65, 67, 68, 81,
}
HALF_LUCKY_NUMBERS = {27, 30, 38, 42, 51, 55, 58, 71, 73, 77, 78}

# 数理个位 → 五行(1,2木 3,4火 5,6土 7,8金 9,0水)
NUMBER_WUXING = {1: "木", 2: "木", 3: "火", 4: "火", 5: "土", 6: "土", 7: "金", 8: "金", 9: "水", 0: "水"}

SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def _luck_of_number(n: int) -> str:
    """数理吉凶(>81 折回 1-81)"""
    n = (n - 1) % 81 + 1
    if n in LUCKY_NUMBERS:
        return "吉"
    if n in HALF_LUCKY_NUMBERS:
        return "半吉"
    return "凶"


def _wuxing_of_number(n: int) -> str:
    """数理个位 → 五行"""
    return NUMBER_WUXING[n % 10]


@dataclass
class SancaiResult:
    """三才五格计算结果"""

    strokes: list[int] = field(default_factory=list)  # 每个字笔画(姓+名)
    estimated_chars: list[str] = field(default_factory=list)  # 笔画为估计值的字
    tian_ge: int = 0  # 天格
    ren_ge: int = 0  # 人格
    di_ge: int = 0  # 地格
    wai_ge: int = 0  # 外格
    zong_ge: int = 0  # 总格
    sancai: str = ""  # 三才配置, 如 "土木水"
    sancai_score: int = 0  # 三才配置得分 0-100
    grid_lucks: dict[str, str] = field(default_factory=dict)  # 各格吉凶
    score: int = 0  # 综合得分 0-100

    def summary(self) -> str:
        return (
            f"五格: 天{self.tian_ge} 人{self.ren_ge} 地{self.di_ge} "
            f"外{self.wai_ge} 总{self.zong_ge}; 三才{self.sancai}; "
            f"综合评分{self.score}分"
        )


def _pair_score(upper: str, lower: str) -> int:
    """三才相邻两行生克关系得分(上=上格五行, 下=下格五行)"""
    if upper == lower:
        return 30  # 比和
    if SHENG[upper] == lower:
        return 28  # 上生下
    if SHENG[lower] == upper:
        return 26  # 下生上(相生)
    if KE[upper] == lower:
        return -22  # 上克下
    return -28  # 下克上


def evaluate_name(surname: str, given: str) -> SancaiResult:
    """计算姓名三才五格

    :param surname: 姓氏(支持单姓/复姓)
    :param given: 名(不含姓, 支持单名/双名)
    :return: SancaiResult
    """
    s_chars = list(surname)
    g_chars = list(given)
    s_strokes: list[int] = []
    g_strokes: list[int] = []
    estimated: list[str] = []
    for ch in s_chars + g_chars:
        n, exact = stroke_of(ch)
        (s_strokes if ch in s_chars else g_strokes).append(n)
        if not exact:
            estimated.append(ch)

    # 五格计算(姓名学标准公式)
    tian = sum(s_strokes) + 1 if len(s_chars) == 1 else sum(s_strokes)
    ren = s_strokes[-1] + (g_strokes[0] if g_strokes else 0)
    di = sum(g_strokes) + (1 if len(g_chars) == 1 else 0)
    zong = sum(s_strokes) + sum(g_strokes)
    if len(s_chars) == 1 and len(g_chars) == 1:
        wai = 2
    else:
        wai = max(zong - ren + 1, 1)

    # 三才: 天/人/地格个位数五行
    wx_tian, wx_ren, wx_di = _wuxing_of_number(tian), _wuxing_of_number(ren), _wuxing_of_number(di)
    sancai = wx_tian + wx_ren + wx_di
    sancai_score = max(5, min(100, 55 + _pair_score(wx_tian, wx_ren) + _pair_score(wx_ren, wx_di)))

    grid_lucks = {
        "天格": _luck_of_number(tian),
        "人格": _luck_of_number(ren),
        "地格": _luck_of_number(di),
        "外格": _luck_of_number(wai),
        "总格": _luck_of_number(zong),
    }
    # 数理得分: 吉92 半吉72 凶45, 五格均值与三才分加权
    num_score = {"吉": 92, "半吉": 72, "凶": 45}
    grid_avg = sum(num_score[v] for v in grid_lucks.values()) / 5
    total = round(grid_avg * 0.6 + sancai_score * 0.4)

    return SancaiResult(
        strokes=s_strokes + g_strokes,
        estimated_chars=estimated,
        tian_ge=tian,
        ren_ge=ren,
        di_ge=di,
        wai_ge=wai,
        zong_ge=zong,
        sancai=sancai,
        sancai_score=sancai_score,
        grid_lucks=grid_lucks,
        score=total,
    )
