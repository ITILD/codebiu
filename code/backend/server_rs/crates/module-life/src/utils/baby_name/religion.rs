//! 宗教文化参考推算(对齐 Python religion.py, 基于宝宝出生日期的经典民俗对应, 纯程序计算)
//!
//! - 佛教: 生肖本命佛(十二生肖守护佛, 按立春分界年支取)
//! - 道教: 本命太岁星君(六十甲子值年太岁, 按年柱干支取)
//! - 基督: 出生季节的圣经意象(春新生/夏丰盛/秋感恩/冬平安)

use common::utils::error::AppError;
use chrono::Datelike;

use super::almanac::{GAN, get_zodiac, parse_birth_date, year_pillar, zhi_char};
use crate::do_::almanac::{BuddhismInfo, ChristianInfo, TaoismInfo};

/// 生肖 → (本命佛, 寓意, 佛家意趣宜用字)
fn benming_buddha(zodiac: &str) -> (&'static str, &'static str, &'static str) {
    match zodiac {
        "鼠" => ("千手观音菩萨", "慈悲无量, 救护众生", "慈、悲、护、莲"),
        "牛" => ("虚空藏菩萨", "智慧功德如虚空藏, 广大无边", "慧、藏、容、智"),
        "虎" => ("虚空藏菩萨", "智慧功德如虚空藏, 广大无边", "慧、藏、容、智"),
        "兔" => ("文殊菩萨", "智慧辩才第一, 启迪心智", "慧、睿、明、思"),
        "龙" => ("普贤菩萨", "行愿广大, 践行不辍", "贤、行、愿、善"),
        "蛇" => ("普贤菩萨", "行愿广大, 践行不辍", "贤、行、愿、善"),
        "马" => ("大势至菩萨", "以智慧光普照一切, 势至圆满", "志、明、光、达"),
        "羊" => ("大日如来", "光明遍照, 无所不至", "昭、曦、明、辉"),
        "猴" => ("大日如来", "光明遍照, 无所不至", "昭、曦、明、辉"),
        "鸡" => ("不动尊菩萨", "坚如金刚, 不为烦恼所动", "恒、坚、定、毅"),
        "狗" => ("阿弥陀佛", "无量光无量寿, 安乐自在", "安、康、宁、寿"),
        "猪" => ("阿弥陀佛", "无量光无量寿, 安乐自在", "安、康、宁、寿"),
        _ => ("", "", ""),
    }
}

/// 本命佛推算(按立春分界生肖取守护佛)
pub fn get_benming_buddha(birth_date: &str) -> Result<BuddhismInfo, AppError> {
    let zodiac = get_zodiac(birth_date)?;
    let (buddha, meaning, chars) = benming_buddha(&zodiac);
    Ok(BuddhismInfo {
        zodiac: zodiac.clone(),
        buddha: buddha.to_string(),
        meaning: meaning.to_string(),
        hint_chars: chars.to_string(),
        summary: format!("生肖{zodiac}本命佛为{buddha}, {meaning}; 佛家意趣宜用字: {chars}"),
    })
}

/// 六十甲子太岁星君名(循环序, 甲子起; 各典籍译名略有出入, 此处取通行说法)
const TAI_SUI_STARS: [&str; 60] = [
    "金辨", "陈材", "耿章", "沈兴", "赵达", "郭灿", "王济", "李素", "刘旺", "康志",
    "施广", "任保", "郭嘉", "汪文", "鲁先", "龙仲", "董德", "郑但", "陆明", "魏仁",
    "方章", "蒋崇", "白敏", "封济", "郑堂", "傅佑", "邬桓", "范宁", "彭泰", "徐斿",
    "章词", "杨仙", "管仲", "唐杰", "姜武", "谢寿", "虞起", "杨信", "贺谔", "皮时",
    "李诚", "吴遂", "文折", "缪丙", "俞志", "程宝", "倪秘", "叶坚", "丘德", "林朴",
    "张朝", "万清", "辛亚", "易彦", "黎卿", "傅赏", "毛梓", "政文", "洪充", "虞程",
];

/// 由干支序求六十甲子循环位(满足 i%10=gan 且 i%12=zhi, 0≤i<60)
fn ganzhi_cycle_index(gan: usize, zhi: usize) -> usize {
    (0..60)
        .find(|i| i % 10 == gan && i % 12 == zhi)
        .expect("合法干支组合必在六十甲子中")
}

/// 本命太岁推算(按立春分界年柱干支取值年太岁星君)
pub fn get_taishi(birth_date: &str) -> Result<TaoismInfo, AppError> {
    let d = parse_birth_date(birth_date)?;
    let (y_gan, y_zhi) = year_pillar(d, None);
    // 干支 = GAN[y_gan] + ZHI[y_zhi]
    let gan_c = GAN.chars().nth(y_gan).expect("天干表长度固定");
    let zhi_c = zhi_char(y_zhi);
    let ganzhi = format!("{gan_c}{zhi_c}");
    // 六十甲子值年太岁星君
    let star = TAI_SUI_STARS[ganzhi_cycle_index(y_gan, y_zhi)];
    let meaning = "太岁为值年之神, 传统以为敬太岁纳吉迎祥, 名字可取道家清静自然意趣";
    let hint_chars = "清、然、朴、云、鹤、宁、玄、虚";
    Ok(TaoismInfo {
        year_ganzhi: ganzhi.clone(),
        taishi: format!("{star}大将军"),
        meaning: meaning.to_string(),
        hint_chars: hint_chars.to_string(),
        summary: format!("年柱{ganzhi}本命太岁为{star}大将军; 道家意趣宜用字: 清、然、朴、云、鹤"),
    })
}

/// 季节 → (季节名由键给出, 圣经主题, 经文, 经文出处, 意象宜用字)
fn christian_season(season: &str) -> (&'static str, &'static str, &'static str, &'static str) {
    match season {
        "春" => (
            "新生与复活",
            "若有人在基督里, 他就是新造的人, 旧事已过, 都变成新的了",
            "《哥林多后书》5:17",
            "恩、新、望、晨",
        ),
        "夏" => (
            "丰盛与活水",
            "我来了, 是要叫人得生命, 并且得的更丰盛",
            "《约翰福音》10:10",
            "恩、乐、沛、沐",
        ),
        "秋" => (
            "感恩与收获",
            "那带种流泪出去的, 必要欢欢乐乐地带禾捆回来",
            "《诗篇》126:6",
            "恩、颂、嘉、实",
        ),
        _ => (
            "平安与以马内利",
            "在至高之处荣耀归与神, 在地上平安归与他所喜悦的人",
            "《路加福音》2:14",
            "安、平、宁、曙",
        ),
    }
}

/// 圣经意象推算(按出生季节取对应圣经主题与祝福经文)
pub fn get_christian_theme(birth_date: &str) -> Result<ChristianInfo, AppError> {
    let d = parse_birth_date(birth_date)?;
    let season = match d.month() {
        3..=5 => "春",
        6..=8 => "夏",
        9..=11 => "秋",
        _ => "冬",
    };
    let (theme, verse, source, chars) = christian_season(season);
    Ok(ChristianInfo {
        season: season.to_string(),
        theme: theme.to_string(),
        verse: format!("「{verse}」—— {source}"),
        hint_chars: chars.to_string(),
        summary: format!("生于{season}季, 圣经意象为{theme}; 祝福意趣宜用字: {chars}"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn buddha_by_zodiac() {
        // 2024 甲辰龙年 → 普贤菩萨
        let info = get_benming_buddha("2024-06-01").unwrap();
        assert_eq!(info.zodiac, "龙");
        assert_eq!(info.buddha, "普贤菩萨");
        assert!(info.summary.contains("普贤菩萨"));
    }

    #[test]
    fn taishi_by_year_ganzhi() {
        // 2024 甲辰年: 甲辰在六十甲子序 40 → 太岁 "李诚大将军"
        let info = get_taishi("2024-06-01").unwrap();
        assert_eq!(info.year_ganzhi, "甲辰");
        assert_eq!(info.taishi, "李诚大将军");
    }

    #[test]
    fn christian_seasons() {
        assert_eq!(get_christian_theme("2024-04-01").unwrap().season, "春");
        assert_eq!(get_christian_theme("2024-07-01").unwrap().season, "夏");
        assert_eq!(get_christian_theme("2024-10-01").unwrap().season, "秋");
        assert_eq!(get_christian_theme("2024-12-25").unwrap().season, "冬");
        let c = get_christian_theme("2024-12-25").unwrap();
        assert!(c.verse.contains("《路加福音》2:14"));
    }
}
