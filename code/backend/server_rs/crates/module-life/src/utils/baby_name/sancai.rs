//! 三才五格计算(对齐 Python sancai.py, 姓名学经典算法)
//!
//! 五格剖象法:
//! - 天格: 单姓 = 姓氏笔画 + 1; 复姓 = 姓氏各字笔画之和
//! - 人格: 姓氏末字笔画 + 名字首字笔画
//! - 地格: 名字笔画之和(单名 + 1)
//! - 外格: 总格 - 人格 + 1(单姓单名固定为 2)
//! - 总格: 姓名全部笔画之和
//! 数理吉凶按 81 数理表(超 81 取模)。三才 = 天/人/地格个位数的五行配置,
//! 按生克关系评分(相生比和为吉, 相克为凶)。

use serde::Serialize;

use super::strokes::stroke_of;

/// 81 数理吉凶表(主流版本)
const LUCKY_NUMBERS: [u32; 35] = [
    1, 3, 5, 6, 7, 8, 11, 13, 15, 16, 17, 18, 21, 23, 24, 25, 29, 31, 32, 33, 35, 37, 39, 41, 45,
    47, 48, 52, 57, 61, 63, 65, 67, 68, 81,
];
/// 半吉数理表
const HALF_LUCKY_NUMBERS: [u32; 11] = [27, 30, 38, 42, 51, 55, 58, 71, 73, 77, 78];

/// 数理个位 → 五行(1,2木 3,4火 5,6土 7,8金 9,0水)
fn wuxing_of_number(n: i32) -> &'static str {
    match n % 10 {
        1 | 2 => "木",
        3 | 4 => "火",
        5 | 6 => "土",
        7 | 8 => "金",
        _ => "水",
    }
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

/// Python round()(银行家舍入: 恰为 .5 时取偶数), 用于对齐评分取整
fn py_round(x: f64) -> i64 {
    let floor = x.floor();
    let diff = x - floor;
    if (diff - 0.5).abs() < f64::EPSILON {
        // 恰为 .5 → 取偶
        let f = floor as i64;
        if f % 2 == 0 { f } else { f + 1 }
    } else {
        x.round() as i64
    }
}

/// 数理吉凶(>81 折回 1-81)
fn luck_of_number(n: i32) -> &'static str {
    let n = ((n - 1).rem_euclid(81) + 1) as u32;
    if LUCKY_NUMBERS.contains(&n) {
        return "吉";
    }
    if HALF_LUCKY_NUMBERS.contains(&n) {
        return "半吉";
    }
    "凶"
}

/// 三才相邻两行生克关系得分(上=上格五行, 下=下格五行)
fn pair_score(upper: &str, lower: &str) -> i32 {
    if upper == lower {
        return 30; // 比和
    }
    if sheng(upper) == lower {
        return 28; // 上生下
    }
    if sheng(lower) == upper {
        return 26; // 下生上(相生)
    }
    if ke(upper) == lower {
        return -22; // 上克下
    }
    -28 // 下克上
}

/// 各格吉凶(键序与 Python 一致: 天格/人格/地格/外格/总格)
#[derive(Debug, Clone, Serialize)]
pub struct GridLucks {
    #[serde(rename = "天格")]
    pub tian: String,
    #[serde(rename = "人格")]
    pub ren: String,
    #[serde(rename = "地格")]
    pub di: String,
    #[serde(rename = "外格")]
    pub wai: String,
    #[serde(rename = "总格")]
    pub zong: String,
}

/// 三才五格计算结果
#[derive(Debug, Clone, Serialize)]
pub struct SancaiResult {
    /// 每个字笔画(姓+名)
    pub strokes: Vec<i32>,
    /// 笔画为估计值的字
    pub estimated_chars: Vec<String>,
    pub tian_ge: i32,
    pub ren_ge: i32,
    pub di_ge: i32,
    pub wai_ge: i32,
    pub zong_ge: i32,
    /// 三才配置, 如 "土木水"
    pub sancai: String,
    /// 三才配置得分 0-100
    pub sancai_score: i32,
    /// 各格吉凶
    pub grid_lucks: GridLucks,
    /// 综合得分 0-100
    pub score: i32,
}

impl SancaiResult {
    /// 一句话总结
    pub fn summary(&self) -> String {
        format!(
            "五格: 天{} 人{} 地{} 外{} 总{}; 三才{}; 综合评分{}分",
            self.tian_ge, self.ren_ge, self.di_ge, self.wai_ge, self.zong_ge, self.sancai, self.score
        )
    }
}

/// 计算姓名三才五格(对齐 Python evaluate_name)
///
/// `surname` 支持单姓/复姓, `given` 支持单名/双名
pub fn evaluate_name(surname: &str, given: &str) -> SancaiResult {
    let s_chars: Vec<char> = surname.chars().collect();
    let g_chars: Vec<char> = given.chars().collect();
    let mut s_strokes: Vec<i32> = Vec::new();
    let mut g_strokes: Vec<i32> = Vec::new();
    let mut estimated: Vec<String> = Vec::new();
    for ch in s_chars.iter().chain(g_chars.iter()) {
        let (n, exact) = stroke_of(*ch);
        if s_chars.contains(ch) {
            s_strokes.push(n);
        } else {
            g_strokes.push(n);
        }
        if !exact {
            estimated.push(ch.to_string());
        }
    }

    // 五格计算(姓名学标准公式)
    let tian = if s_chars.len() == 1 { s_strokes.iter().sum::<i32>() + 1 } else { s_strokes.iter().sum() };
    let ren = s_strokes.last().copied().unwrap_or(0)
        + g_strokes.first().copied().unwrap_or(0);
    let di = g_strokes.iter().sum::<i32>() + if g_chars.len() == 1 { 1 } else { 0 };
    let zong = s_strokes.iter().sum::<i32>() + g_strokes.iter().sum::<i32>();
    let wai = if s_chars.len() == 1 && g_chars.len() == 1 {
        2
    } else {
        (zong - ren + 1).max(1)
    };

    // 三才: 天/人/地格个位数五行
    let wx_tian = wuxing_of_number(tian);
    let wx_ren = wuxing_of_number(ren);
    let wx_di = wuxing_of_number(di);
    let sancai = format!("{wx_tian}{wx_ren}{wx_di}");
    let sancai_score = (55 + pair_score(wx_tian, wx_ren) + pair_score(wx_ren, wx_di))
        .clamp(5, 100);

    let grid_lucks = GridLucks {
        tian: luck_of_number(tian).to_string(),
        ren: luck_of_number(ren).to_string(),
        di: luck_of_number(di).to_string(),
        wai: luck_of_number(wai).to_string(),
        zong: luck_of_number(zong).to_string(),
    };
    // 数理得分: 吉92 半吉72 凶45, 五格均值与三才分加权(Python round 银行家舍入)
    let num_score = |v: &str| match v { "吉" => 92.0, "半吉" => 72.0, _ => 45.0 };
    let grid_avg = (num_score(&grid_lucks.tian)
        + num_score(&grid_lucks.ren)
        + num_score(&grid_lucks.di)
        + num_score(&grid_lucks.wai)
        + num_score(&grid_lucks.zong))
        / 5.0;
    let score = py_round(grid_avg * 0.6 + sancai_score as f64 * 0.4) as i32;

    SancaiResult {
        strokes: s_strokes.into_iter().chain(g_strokes).collect(),
        estimated_chars: estimated,
        tian_ge: tian,
        ren_ge: ren,
        di_ge: di,
        wai_ge: wai,
        zong_ge: zong,
        sancai,
        sancai_score,
        grid_lucks,
        score,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn evaluate_single_surname_single_char() {
        // 王(4) + 明(8): 天5 人12 地9 外2 总12; 三才 土木水
        let r = evaluate_name("王", "明");
        assert_eq!(r.strokes, vec![4, 8]);
        assert_eq!(r.tian_ge, 5);
        assert_eq!(r.ren_ge, 12);
        assert_eq!(r.di_ge, 9);
        assert_eq!(r.wai_ge, 2);
        assert_eq!(r.zong_ge, 12);
        assert_eq!(r.sancai, "土木水");
        // 五格: 天5(吉92) 人12(凶45) 地9(凶45) 外2(凶45) 总12(凶45) → avg=54.4
        // pair(土,木)=下克上-28, pair(木,水)=下生上26 → 55-28+26=53
        assert_eq!(r.sancai_score, 53);
        assert_eq!(r.score, py_round(54.4 * 0.6 + 53.0 * 0.4) as i32); // 53.84 → 54
    }

    #[test]
    fn evaluate_double_char_given() {
        // 王(4) + 小(3)明(8): 天5 人7 地11 外9 总15; 三才 土金木
        let r = evaluate_name("王", "小明");
        assert_eq!(r.strokes, vec![4, 3, 8]);
        assert_eq!(r.tian_ge, 5);
        assert_eq!(r.ren_ge, 7);
        assert_eq!(r.di_ge, 11);
        assert_eq!(r.wai_ge, 9);
        assert_eq!(r.zong_ge, 15);
        assert_eq!(r.sancai, "土金木");
        // 五格: 吉 吉 吉 凶 吉 → avg=(92*4+45)/5=82.6
        // pair(土,金)=上生下28, pair(金,木)=上克下-22 → 55+28-22=61
        assert_eq!(r.sancai_score, 61);
        assert_eq!(r.score, 74);
        assert_eq!(r.summary(), "五格: 天5 人7 地11 外9 总15; 三才土金木; 综合评分74分");
    }

    #[test]
    fn py_round_bankers() {
        // Python round 半数取偶
        assert_eq!(py_round(0.5), 0);
        assert_eq!(py_round(1.5), 2);
        assert_eq!(py_round(2.5), 2);
        assert_eq!(py_round(73.96), 74);
        assert_eq!(py_round(-0.5), 0);
    }
}
