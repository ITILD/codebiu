//! 五行八字分析(对齐 Python wuxing.py): 天干地支五行统计、日主强弱、喜用神(经典简化规则)
//!
//! 喜用神判定采用经典"扶抑法"简化版:
//! - 统计八字(天干4 + 地支主气4)五行个数;
//! - 同类 = 日主五行 + 生日主的五行(印); 异类 = 克/泄/耗日主的五行;
//! - 同类弱于异类 → 身弱, 喜生扶(印星/比劫); 反之身强, 喜克泄耗(官杀/食伤/财星);
//! - 五行有缺(数量为0)优先补缺。
//! 注: 严格喜用神还需结合月令旺衰与刑冲合害, 此处为通用的扶抑近似, 供起名参考。

use common::utils::error::AppError;

use super::almanac::{GAN_WUXING, FourPillars, ZHI_CANGGAN, ZHI_WUXING, get_four_pillars, zhi_char};
use crate::do_::almanac::{CangganItem, FourPillarInfo, WuxingCounts};

/// 五行统计顺序(与 Python WUXING_ORDER 一致: 金木水火土)
const WUXING_ORDER: [&str; 5] = ["金", "木", "水", "火", "土"];

/// 五行名称在统计顺序中的下标
fn wuxing_idx(w: &str) -> usize {
    WUXING_ORDER.iter().position(|x| *x == w).expect("五行名合法")
}

/// 五行相生: A → B
fn sheng(w: &str) -> &'static str {
    match w {
        "木" => "火", "火" => "土", "土" => "金", "金" => "水", "水" => "木", _ => "",
    }
}

/// 五行相克: A 克 B
fn ke(w: &str) -> &'static str {
    match w {
        "木" => "土", "土" => "水", "水" => "火", "火" => "金", "金" => "木", _ => "",
    }
}

/// 按五行名取统计数组中的个数(顺序: 金木水火土)
fn count_at(arr: &[i32; 5], w: &str) -> i32 {
    arr[wuxing_idx(w)]
}

/// 统计八字五行个数(天干4 + 地支主气4)
pub fn count_wuxing(pillars: &FourPillars) -> WuxingCounts {
    let mut counts = [0i32; 5];
    for (gan, zhi) in [pillars.year, pillars.month, pillars.day, pillars.hour] {
        counts[wuxing_idx(GAN_WUXING[gan])] += 1;
        counts[wuxing_idx(ZHI_WUXING[zhi])] += 1;
    }
    WuxingCounts {
        jin: counts[0],
        mu: counts[1],
        shui: counts[2],
        huo: counts[3],
        tu: counts[4],
    }
}

/// 地支藏干明细(供专业展示)
pub fn canggan_detail(pillars: &FourPillars) -> Vec<CangganItem> {
    [pillars.year, pillars.month, pillars.day, pillars.hour]
        .iter()
        .enumerate()
        .map(|(i, p)| CangganItem {
            pillar: pillars.labels()[i].to_string(),
            branch: zhi_char(p.1).to_string(),
            hidden: ZHI_CANGGAN[p.1].to_string(),
        })
        .collect()
}

/// 完整五行八字分析结果(供控制器直接映射响应)
#[derive(Debug)]
pub struct WuxingAnalysis {
    /// 四柱干支(含柱名与五行)
    pub pillars: Vec<FourPillarInfo>,
    pub counts: WuxingCounts,
    pub canggan: Vec<CangganItem>,
    pub day_master: String,
    pub strength: String,
    pub favorable: Vec<String>,
    pub summary: String,
}

/// 完整五行八字分析(对齐 Python analyze_wuxing)
pub fn analyze_wuxing(birth_date: &str, birth_time: &str) -> Result<WuxingAnalysis, AppError> {
    let pillars = get_four_pillars(birth_date, birth_time)?;
    let counts = count_wuxing(&pillars);
    let arr = [counts.jin, counts.mu, counts.shui, counts.huo, counts.tu];
    let day_master = GAN_WUXING[pillars.day.0];
    // 同类: 日主 + 生日主(印); 异类: 其余
    let yin = *WUXING_ORDER
        .iter()
        .find(|w| sheng(w) == day_master)
        .expect("五行相生环完整");
    let same = count_at(&arr, day_master) + count_at(&arr, yin);
    let opposite: i32 = (0..5)
        .filter(|i| WUXING_ORDER[*i] != day_master && WUXING_ORDER[*i] != yin)
        .map(|i| arr[i])
        .sum();
    let strength = if same < opposite { "身弱" } else { "身强" };

    let mut favorable: Vec<String> = Vec::new();
    // 缺失的五行优先补
    let missing: Vec<&str> = (0..5).filter(|i| arr[*i] == 0).map(|i| WUXING_ORDER[i]).collect();
    for w in &missing {
        favorable.push((*w).to_string());
    }
    if strength == "身弱" {
        // 身弱喜生扶: 印星(生日主)与比劫(同日主)
        for w in [yin, day_master] {
            if !favorable.iter().any(|f| f == w) {
                favorable.push(w.to_string());
            }
        }
    } else {
        // 身强喜克泄耗: 官杀(克日主)、食伤(日主生)、财星(日主克), 按八字中数量少者优先(稳定排序)
        let guan = *WUXING_ORDER
            .iter()
            .find(|w| ke(w) == day_master)
            .expect("五行相克环完整");
        let shi = sheng(day_master);
        let cai = ke(day_master);
        let mut drains = [guan, shi, cai];
        drains.sort_by_key(|w| count_at(&arr, w));
        for w in drains {
            if !favorable.iter().any(|f| f == w) {
                favorable.push(w.to_string());
            }
        }
    }

    // 一句话总结(键序与 Python counts.items() 一致: 金木水火土)
    let counts_str = format!(
        "金{}、木{}、水{}、火{}、土{}",
        counts.jin, counts.mu, counts.shui, counts.huo, counts.tu
    );
    let missing_part = if missing.is_empty() {
        "五行不缺。".to_string()
    } else {
        format!("五行缺{}。", missing.join("、"))
    };
    let favorable2: Vec<String> = favorable.iter().take(2).cloned().collect();
    let summary = format!(
        "八字五行: {}; 日主{}{}, {}起名宜补{}属性行。",
        counts_str,
        day_master,
        strength,
        missing_part,
        favorable2.join("、")
    );

    // 四柱干支明细(柱名 + 干支 + 干支五行)
    let names = pillars.names();
    let pairs = [pillars.year, pillars.month, pillars.day, pillars.hour];
    let pillar_infos = names
        .iter()
        .zip(pairs.iter())
        .zip(pillars.labels())
        .map(|((name, p), label)| FourPillarInfo {
            label: label.to_string(),
            ganzhi: name.clone(),
            wuxing: format!("{}{}", GAN_WUXING[p.0], ZHI_WUXING[p.1]),
        })
        .collect();

    Ok(WuxingAnalysis {
        pillars: pillar_infos,
        counts,
        canggan: canggan_detail(&pillars),
        day_master: day_master.to_string(),
        strength: strength.to_string(),
        favorable,
        summary,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn analyze_known_bazi() {
        // 1949-10-01 12:00 甲子日 → 日主甲木; 只断言结构有效性
        let r = analyze_wuxing("1949-10-01", "12:00").unwrap();
        assert_eq!(r.pillars.len(), 4);
        assert_eq!(r.canggan.len(), 4);
        assert_eq!(r.day_master, "木");
        assert!(r.strength == "身强" || r.strength == "身弱");
        assert!(!r.summary.is_empty());
    }
}
