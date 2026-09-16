"""宗教文化参考推算(基于宝宝出生日期的经典民俗对应, 纯程序计算)

- 佛教: 生肖本命佛(十二生肖守护佛, 按立春分界年支取)
- 道教: 本命太岁星君(六十甲子值年太岁, 按年柱干支取)
- 基督: 出生季节的圣经意象(春新生/夏丰盛/秋感恩/冬平安)
"""

import datetime as dt

from module_life.utils.baby_name.almanac import GAN, ZHI, get_zodiac, year_pillar

# ==================== 佛教: 本命佛(生肖守护佛) ====================

# 生肖 -> (本命佛, 寓意, 佛家意趣宜用字)
_BENMING_BUDDHA: dict[str, tuple[str, str, str]] = {
    "鼠": ("千手观音菩萨", "慈悲无量, 救护众生", "慈、悲、护、莲"),
    "牛": ("虚空藏菩萨", "智慧功德如虚空藏, 广大无边", "慧、藏、容、智"),
    "虎": ("虚空藏菩萨", "智慧功德如虚空藏, 广大无边", "慧、藏、容、智"),
    "兔": ("文殊菩萨", "智慧辩才第一, 启迪心智", "慧、睿、明、思"),
    "龙": ("普贤菩萨", "行愿广大, 践行不辍", "贤、行、愿、善"),
    "蛇": ("普贤菩萨", "行愿广大, 践行不辍", "贤、行、愿、善"),
    "马": ("大势至菩萨", "以智慧光普照一切, 势至圆满", "志、明、光、达"),
    "羊": ("大日如来", "光明遍照, 无所不至", "昭、曦、明、辉"),
    "猴": ("大日如来", "光明遍照, 无所不至", "昭、曦、明、辉"),
    "鸡": ("不动尊菩萨", "坚如金刚, 不为烦恼所动", "恒、坚、定、毅"),
    "狗": ("阿弥陀佛", "无量光无量寿, 安乐自在", "安、康、宁、寿"),
    "猪": ("阿弥陀佛", "无量光无量寿, 安乐自在", "安、康、宁、寿"),
}


def get_benming_buddha(birth_date: str) -> dict:
    """本命佛推算(按立春分界生肖取守护佛)

    :param birth_date: 公历出生日期(YYYY-MM-DD)
    :return: 含生肖/本命佛/寓意/宜用字的字典
    """
    zodiac = get_zodiac(birth_date)
    buddha, meaning, chars = _BENMING_BUDDHA.get(zodiac, ("", "", ""))
    return {
        "zodiac": zodiac,
        "buddha": buddha,
        "meaning": meaning,
        "hint_chars": chars,
        "summary": f"生肖{zodiac}本命佛为{buddha}, {meaning}; 佛家意趣宜用字: {chars}",
    }


# ==================== 道教: 本命太岁(六十甲子值年太岁星君) ====================

# 六十甲子太岁星君名(循环序, 甲子起; 各典籍译名略有出入, 此处取通行说法)
_TAI_SUI_STARS: list[str] = [
    "金辨", "陈材", "耿章", "沈兴", "赵达", "郭灿", "王济", "李素", "刘旺", "康志",
    "施广", "任保", "郭嘉", "汪文", "鲁先", "龙仲", "董德", "郑但", "陆明", "魏仁",
    "方章", "蒋崇", "白敏", "封济", "郑堂", "傅佑", "邬桓", "范宁", "彭泰", "徐斿",
    "章词", "杨仙", "管仲", "唐杰", "姜武", "谢寿", "虞起", "杨信", "贺谔", "皮时",
    "李诚", "吴遂", "文折", "缪丙", "俞志", "程宝", "倪秘", "叶坚", "丘德", "林朴",
    "张朝", "万清", "辛亚", "易彦", "黎卿", "傅赏", "毛梓", "政文", "洪充", "虞程",
]

# 干支 -> 太岁星君(按六十甲子循环序构建)
_TAI_SUI_MAP: dict[str, str] = {
    GAN[i % 10] + ZHI[i % 12]: _TAI_SUI_STARS[i] + "大将军" for i in range(60)
}


def get_taishi(birth_date: str) -> dict:
    """本命太岁推算(按立春分界年柱干支取值年太岁星君)

    :param birth_date: 公历出生日期(YYYY-MM-DD)
    :return: 含年柱干支/太岁星君/寓意/宜用字的字典
    """
    y_gan, y_zhi = year_pillar(dt.date.fromisoformat(birth_date))
    ganzhi = GAN[y_gan] + ZHI[y_zhi]
    star = _TAI_SUI_MAP.get(ganzhi, "")
    return {
        "year_ganzhi": ganzhi,
        "taishi": star,
        "meaning": "太岁为值年之神, 传统以为敬太岁纳吉迎祥, 名字可取道家清静自然意趣",
        "hint_chars": "清、然、朴、云、鹤、宁、玄、虚",
        "summary": f"年柱{ganzhi}本命太岁为{star}; 道家意趣宜用字: 清、然、朴、云、鹤",
    }


# ==================== 基督: 出生季节圣经意象 ====================

# 季节 -> (季节名, 圣经主题, 经文, 经文出处, 意象宜用字)
_CHRISTIAN_SEASON: dict[str, tuple[str, str, str, str]] = {
    "春": (
        "新生与复活",
        "若有人在基督里, 他就是新造的人, 旧事已过, 都变成新的了",
        "《哥林多后书》5:17",
        "恩、新、望、晨",
    ),
    "夏": (
        "丰盛与活水",
        "我来了, 是要叫人得生命, 并且得的更丰盛",
        "《约翰福音》10:10",
        "恩、乐、沛、沐",
    ),
    "秋": (
        "感恩与收获",
        "那带种流泪出去的, 必要欢欢乐乐地带禾捆回来",
        "《诗篇》126:6",
        "恩、颂、嘉、实",
    ),
    "冬": (
        "平安与以马内利",
        "在至高之处荣耀归与神, 在地上平安归与他所喜悦的人",
        "《路加福音》2:14",
        "安、平、宁、曙",
    ),
}


def get_christian_theme(birth_date: str) -> dict:
    """圣经意象推算(按出生季节取对应圣经主题与祝福经文)

    :param birth_date: 公历出生日期(YYYY-MM-DD)
    :return: 含季节/主题/经文/宜用字的字典
    """
    month = dt.date.fromisoformat(birth_date).month
    season = "春" if 3 <= month <= 5 else "夏" if 6 <= month <= 8 else "秋" if 9 <= month <= 11 else "冬"
    theme, verse, source, chars = _CHRISTIAN_SEASON[season]
    return {
        "season": season,
        "theme": theme,
        "verse": f"「{verse}」—— {source}",
        "hint_chars": chars,
        "summary": f"生于{season}季, 圣经意象为{theme}; 祝福意趣宜用字: {chars}",
    }
