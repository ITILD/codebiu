//! 星座计算(对齐 Python constellation.py): 按公历出生日期严格划分十二星座
//!
//! 分界日期为占星学通用的太阳黄经分界(每年因岁差仅浮动 1 天内, 采用固定区间标准)。

use chrono::{Datelike, NaiveDate};
use common::utils::error::AppError;

use super::almanac::parse_birth_date;
use crate::do_::almanac::ConstellationInfo;

/// 星座表: (名称, 起始月-日, 元素, 特质摘要)
const CONSTELLATIONS: [(&str, (u32, u32), &str, &str); 12] = [
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
];

/// 月日 → 可比较键
fn date_key(month: u32, day: u32) -> u32 {
    month * 100 + day
}

/// 按公历日期严格划分星座
pub fn get_constellation(birth_date: &str) -> Result<ConstellationInfo, AppError> {
    let d: NaiveDate = parse_birth_date(birth_date)?;
    let key = date_key(d.month(), d.day());
    // 各星座起始边界(当前星座名对应起点, 水瓶座起 1/20 环形判断)
    for (i, (name, start, element, traits)) in CONSTELLATIONS.iter().enumerate() {
        let (_, next_start, _, _) = CONSTELLATIONS[(i + 1) % 12];
        let s_key = date_key(start.0, start.1);
        let n_key = date_key(next_start.0, next_start.1);
        if s_key <= key && key < n_key {
            return Ok(ConstellationInfo {
                name: name.to_string(),
                date_range: format!(
                    "{}月{}日-{}月{}日",
                    start.0,
                    start.1,
                    next_start.0,
                    next_start.1 - 1
                ),
                element: element.to_string(),
                traits: traits.to_string(),
                summary: format!(
                    "星座: {name}({}月{}日-{}月{}日), 属{element}象星座。特质: {traits}",
                    start.0,
                    start.1,
                    next_start.0,
                    next_start.1 - 1
                ),
            });
        }
    }
    // 12/22 以后到次年 1/19 之间属于摩羯座(环形区间兜底)
    let (name, _, element, traits) = CONSTELLATIONS[9];
    Ok(ConstellationInfo {
        name: name.to_string(),
        date_range: "12月22日-1月19日".to_string(),
        element: element.to_string(),
        traits: traits.to_string(),
        summary: format!("星座: {name}(12月22日-1月19日), 属{element}象星座。特质: {traits}"),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constellation_boundaries() {
        // 白羊座 3/21 起; 边界日 4/19 仍属白羊, 4/20 起金牛
        assert_eq!(get_constellation("2000-03-21").unwrap().name, "白羊座");
        assert_eq!(get_constellation("2000-04-19").unwrap().name, "白羊座");
        assert_eq!(get_constellation("2000-04-20").unwrap().name, "金牛座");
        // 环形兜底: 摩羯座 12/22 - 1/19
        assert_eq!(get_constellation("2000-01-05").unwrap().name, "摩羯座");
        assert_eq!(get_constellation("2000-12-25").unwrap().name, "摩羯座");
        assert_eq!(get_constellation("2000-01-19").unwrap().name, "摩羯座");
        assert_eq!(get_constellation("2000-01-20").unwrap().name, "水瓶座");
        // 日期区间描述(白羊座 3月21日-4月19日)
        assert_eq!(get_constellation("2000-03-25").unwrap().date_range, "3月21日-4月19日");
    }
}
