//! 历法干支模块(对齐 Python almanac.py): 节气天文解、四柱八字(年/月/日/时干支)、生肖
//!
//! 经典算法说明:
//! - 日柱: 以儒略日数(JDN)为基准, 甲子日满足 (JDN - 11) % 60 == 0。
//!   双锚点互证: 1900-01-01 为甲戌日(序10)、1949-10-01 为甲子日(序0)。
//! - 年柱: 以立春为界, 立春前属前一年 (子平术正统分界)。
//! - 月柱: 以十二"节"分界, 月干由年干五虎遁得出。
//! - 时柱: 十二时辰按小时分界, 时干由日干五鼠遁得出;
//!   23:00 后按主流子平惯例归入次日子时(日柱同步进位)。
//! - 节气: 采用寿星天文历天文算法(shou_xing), 节气时刻精度优于 1 分钟。

use chrono::{Datelike, NaiveDate, NaiveDateTime};
use common::utils::error::AppError;

use super::shou_xing::solar_term_time;

/// 天干
pub const GAN: &str = "甲乙丙丁戊己庚辛壬癸";
/// 地支
pub const ZHI: &str = "子丑寅卯辰巳午未申酉戌亥";
/// 天干五行(与 GAN 一一对应)
pub const GAN_WUXING: [&str; 10] = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"];
/// 地支五行(主气, 与 ZHI 一一对应)
pub const ZHI_WUXING: [&str; 12] = [
    "水", "土", "木", "木", "土", "火", "火", "土", "金", "金", "土", "水",
];
/// 地支藏干(主气在前)
pub const ZHI_CANGGAN: [&str; 12] = [
    "癸", "己癸辛", "甲丙戊", "乙", "戊乙癸", "丙庚戊", "丁己", "己丁乙", "庚壬戊", "辛",
    "戊辛丁", "壬甲",
];
/// 生肖(按年支)
pub const ZODIAC: &str = "鼠牛虎兔龙蛇马羊猴鸡狗猪";

/// 十二"节"(月柱分界): (节气名, 对应公历月)
const JIE_ORDER: [(&str, u32); 12] = [
    ("立春", 2), ("惊蛰", 3), ("清明", 4), ("立夏", 5), ("芒种", 6), ("小暑", 7),
    ("立秋", 8), ("白露", 9), ("寒露", 10), ("立冬", 11), ("大雪", 12), ("小寒", 1),
];
/// 月支: 寅月起正月, 月支序号(地支索引) = 2 + 节序 (mod 12)
const JIE_MONTH_ZHI: [usize; 12] = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 0, 1];

/// 取干/支字符(越界由调用方保证, 表长固定安全)
pub fn gan_char(idx: usize) -> char {
    GAN.chars().nth(idx % 10).expect("天干表长度固定为10")
}

/// 取地支字符
pub fn zhi_char(idx: usize) -> char {
    ZHI.chars().nth(idx % 12).expect("地支表长度固定为12")
}

/// 24节气太阳视黄经(度): 春分=0°, 每气15°
fn term_deg(term: &str) -> Option<f64> {
    Some(match term {
        "春分" => 0.0, "清明" => 15.0, "谷雨" => 30.0, "立夏" => 45.0,
        "小满" => 60.0, "芒种" => 75.0, "夏至" => 90.0, "小暑" => 105.0,
        "大暑" => 120.0, "立秋" => 135.0, "处暑" => 150.0, "白露" => 165.0,
        "秋分" => 180.0, "寒露" => 195.0, "霜降" => 210.0, "立冬" => 225.0,
        "小雪" => 240.0, "大雪" => 255.0, "冬至" => 270.0, "小寒" => 285.0,
        "大寒" => 300.0, "立春" => 315.0, "雨水" => 330.0, "惊蛰" => 345.0,
        _ => return None,
    })
}

/// 公历日期 → 儒略日数 JDN(标准 Gregorian 公式)
fn jdn(date: NaiveDate) -> i32 {
    let (y, m, d) = (date.year(), date.month() as i32, date.day() as i32);
    let a = (14 - m) / 12;
    let y = y + 4800 - a;
    let m = m + 12 * a - 3;
    d + (153 * m + 2) / 5 + 365 * y + y / 4 - y / 100 + y / 400 - 32045
}

/// 某年某节气的精确时刻(北京时间, 天文解, 精度优于1分钟)
fn jie_time(year: i32, term: &str) -> NaiveDateTime {
    let deg = term_deg(term).expect("节气名合法");
    solar_term_time(year, deg)
}

/// 出生时刻: hour=None 视为当日末尾(仅按日粒度做分界)
fn birth_moment(date: NaiveDate, hour: Option<u32>) -> NaiveDateTime {
    date.and_hms_opt(hour.unwrap_or(23), if hour.is_none() { 59 } else { 0 }, 0)
        .expect("合法时刻")
}

/// 日柱干支序号(0=甲子 ... 59=癸亥)
pub fn day_ganzhi_index(date: NaiveDate) -> i32 {
    (jdn(date) - 11).rem_euclid(60)
}

/// 年柱 (干序, 支序): 以立春(精确到时刻)为界, 立春前属前一年
pub fn year_pillar(date: NaiveDate, hour: Option<u32>) -> (usize, usize) {
    let mut year = date.year();
    if birth_moment(date, hour) < jie_time(year, "立春") {
        year -= 1;
    }
    let idx = (year - 4).rem_euclid(60);
    ((idx % 10) as usize, (idx % 12) as usize)
}

/// 月柱 (干序, 支序): 十二节分界(精确到时刻) + 五虎遁取月干
pub fn month_pillar(date: NaiveDate, hour: Option<u32>) -> (usize, usize) {
    let birth = birth_moment(date, hour);
    let year = date.year();
    // 依次判断日期落在哪个节之后(从大雪倒序到立春; 小寒已单独处理)
    let zhi_idx: usize = if birth < jie_time(year, "小寒") {
        // 小寒之前(1月上旬)属于上一年的子月(大雪之后)
        0
    } else {
        let mut zhi = 1usize; // 默认丑月(小寒~立春)
        for i in (0..11).rev() {
            let (term, month) = JIE_ORDER[i];
            if date.month() > month || (date.month() == month && birth >= jie_time(year, term)) {
                zhi = JIE_MONTH_ZHI[i];
                break;
            }
        }
        zhi
    };
    // 五虎遁: 年干甲己→丙寅起, 乙庚→戊寅, 丙辛→庚寅, 丁壬→壬寅, 戊癸→甲寅
    let year_gan = year_pillar(date, hour).0;
    let first_gan = (2 * (year_gan % 5) + 2) % 10;
    // 月支相对寅的偏移
    let offset = (zhi_idx + 10) % 12;
    ((first_gan + offset) % 10, zhi_idx)
}

/// 时支序号: 23/0→子, 1-2→丑, ... 21-22→亥
pub fn hour_zhi_index(hour: u32) -> usize {
    (((hour + 1) / 2) % 12) as usize
}

/// 考虑晚子时(23点后归次日)的日柱干支序号
pub fn day_pillar_for_hour(date: NaiveDate, hour: u32) -> i32 {
    let mut idx = day_ganzhi_index(date);
    if hour >= 23 {
        idx = (idx + 1) % 60;
    }
    idx
}

/// 时柱 (干序, 支序): 五鼠遁取时干
pub fn hour_pillar(date: NaiveDate, hour: u32) -> (usize, usize) {
    let zhi = hour_zhi_index(hour);
    let day_gan = (day_pillar_for_hour(date, hour) % 10) as usize;
    // 五鼠遁: 日干甲己→甲子起, 乙庚→丙子, 丙辛→戊子, 丁壬→庚子, 戊癸→壬子
    let first_gan = (2 * (day_gan % 5)) % 10;
    ((first_gan + zhi) % 10, zhi)
}

/// 四柱八字: 每柱为 (干序, 支序)
#[derive(Debug, Clone, Copy)]
pub struct FourPillars {
    pub year: (usize, usize),
    pub month: (usize, usize),
    pub day: (usize, usize),
    pub hour: (usize, usize),
}

impl FourPillars {
    /// 单柱干支名, 如 丙午
    fn name(pillar: (usize, usize)) -> String {
        format!("{}{}", gan_char(pillar.0), zhi_char(pillar.1))
    }

    /// 四柱干支名, 如 ["丙午","丁酉","庚辰","戊辰"]
    pub fn names(&self) -> Vec<String> {
        [self.year, self.month, self.day, self.hour]
            .iter()
            .map(|p| Self::name(*p))
            .collect()
    }

    /// 柱名标签(年柱/月柱/日柱/时柱)
    pub fn labels(&self) -> [&'static str; 4] {
        ["年柱", "月柱", "日柱", "时柱"]
    }
}

/// 解析公历出生日期(YYYY-MM-DD)
pub fn parse_birth_date(birth_date: &str) -> Result<NaiveDate, AppError> {
    NaiveDate::parse_from_str(birth_date.trim(), "%Y-%m-%d")
        .map_err(|_| AppError::business(format!("出生日期格式无效: {birth_date}, 应为 YYYY-MM-DD")))
}

/// 由出生日期(YYYY-MM-DD)与时间(HH:mm)推算四柱八字
///
/// 未提供精确时间时按午时兜底; 晚子时(23点后)归次日子时, 日柱同步进位
pub fn get_four_pillars(birth_date: &str, birth_time: &str) -> Result<FourPillars, AppError> {
    let d = parse_birth_date(birth_date)?;
    // Python: try h, m = birth_time.split(":"); hour = int(h) except ValueError → 12
    let hour: u32 = match birth_time.split_once(':') {
        Some((h, _)) => h.trim().parse().unwrap_or(12),
        None => 12,
    };
    if hour > 23 {
        return Err(AppError::business(format!(
            "出生时间无效: {birth_time}, 小时应在0-23之间"
        )));
    }
    // 晚子时(23点后)归次日子时, 日柱同步进位, 保证与时柱五鼠遁一致
    let day_idx = day_pillar_for_hour(d, hour);
    Ok(FourPillars {
        year: year_pillar(d, Some(hour)),
        month: month_pillar(d, Some(hour)),
        day: ((day_idx % 10) as usize, (day_idx % 12) as usize),
        hour: hour_pillar(d, hour),
    })
}

/// 按年柱地支取生肖(立春分界, 对齐 Python ZODIAC[支序])
pub fn get_zodiac(birth_date: &str) -> Result<String, AppError> {
    let d = parse_birth_date(birth_date)?;
    let zhi = year_pillar(d, None).1;
    Ok(ZODIAC
        .chars()
        .nth(zhi % 12)
        .expect("生肖表长度固定为12")
        .to_string())
}

/// 生肖传统宜用字根(起名民俗参考, 对齐 Python ZODIAC_HINTS)
pub fn zodiac_hint(zodiac: &str) -> &'static str {
    match zodiac {
        "鼠" => "宜用宀、米、豆、金、玉等字根; 慎用日、火、人字根",
        "牛" => "宜用艹、田、禾、金、谷等字根; 慎用马、山字根",
        "虎" => "宜用山、林、木、王、君等字根; 慎用日、蛇形字根",
        "兔" => "宜用艹、月、禾、口、木等字根; 慎用日、心、辰龙字根",
        "龙" => "宜用氵、云、雨、日、月、王等字根; 慎用犬、田字根",
        "蛇" => "宜用口、木、田、山、鱼等字根; 慎用氵、亥猪字根",
        "马" => "宜用艹、木、禾、龙、寅虎等字根; 慎用子、牛、山字根",
        "羊" => "宜用艹、木、豆、米、几等字根; 慎用丑牛、心字根",
        "猴" => "宜用木、水、亻、王、子等字根; 慎用寅虎、亥猪字根",
        "鸡" => "宜用米、豆、山、艹、金等字根; 慎用卯兔、犬字根",
        "狗" => "宜用亻、入、艹、金、玉等字根; 慎用鸡形、田字根",
        "猪" => "宜用宀、米、豆、金、木等字根; 慎用示(祭祀)、蛇形字根",
        _ => "",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn day_pillar_double_anchors() {
        // 双锚点: 1900-01-01 甲戌(序10) / 1949-10-01 甲子(序0)
        let d1 = NaiveDate::from_ymd_opt(1900, 1, 1).unwrap();
        assert_eq!(day_ganzhi_index(d1), 10);
        let d2 = NaiveDate::from_ymd_opt(1949, 10, 1).unwrap();
        assert_eq!(day_ganzhi_index(d2), 0);
    }

    #[test]
    fn year_pillar_lichun_boundary() {
        // 2024 立春约 02-04 16:26: 之前属癸卯, 之后属甲辰
        let before = NaiveDate::from_ymd_opt(2024, 2, 4).unwrap();
        assert_eq!(year_pillar(before, Some(16)), (9, 3)); // 癸卯
        assert_eq!(year_pillar(before, Some(17)), (0, 4)); // 甲辰
        let d = NaiveDate::from_ymd_opt(2024, 6, 1).unwrap();
        assert_eq!(year_pillar(d, None), (0, 4)); // 甲辰年
    }

    #[test]
    fn hour_pillar_wushu_dun() {
        // 1949-10-01 甲子日午时: 五鼠遁 甲己→甲子起, 顺推午时为庚午
        let d = NaiveDate::from_ymd_opt(1949, 10, 1).unwrap();
        assert_eq!(hour_pillar(d, 12), (6, 6));
        // 晚子时: 23点日柱进位为乙丑日, 时干五鼠遁 乙庚→丙子起
        assert_eq!(day_pillar_for_hour(d, 23), 1);
        assert_eq!(hour_pillar(d, 23), (2, 0));
    }

    #[test]
    fn zodiac_by_lichun() {
        // 2024-06-01 → 龙; 2024-02-01(立春前) → 兔(2023 癸卯)
        assert_eq!(get_zodiac("2024-06-01").unwrap(), "龙");
        assert_eq!(get_zodiac("2024-02-01").unwrap(), "兔");
    }
}
