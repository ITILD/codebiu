//! 历法/参考体系推算结果(对齐 Python module_life/utils/baby_name/do/baby_name.py 的非表响应模型)
//!
//! 仅含推算输出结构, 计算逻辑在 utils/baby_name 算法模块, 编排在 services 层。

use serde::Serialize;

/// 单柱干支信息(FourPillarInfo)
#[derive(Debug, Serialize)]
pub struct FourPillarInfo {
    /// 柱名(年柱/月柱/日柱/时柱)
    pub label: String,
    /// 干支, 如 丙午
    pub ganzhi: String,
    /// 干支五行, 如 火火
    pub wuxing: String,
}

/// 五行个数统计(键序与 Python 一致: 金木水火土)
#[derive(Debug, Serialize)]
pub struct WuxingCounts {
    #[serde(rename = "金")]
    pub jin: i32,
    #[serde(rename = "木")]
    pub mu: i32,
    #[serde(rename = "水")]
    pub shui: i32,
    #[serde(rename = "火")]
    pub huo: i32,
    #[serde(rename = "土")]
    pub tu: i32,
}

/// 地支藏干明细单项({pillar, branch, hidden})
#[derive(Debug, Serialize)]
pub struct CangganItem {
    /// 柱名
    pub pillar: String,
    /// 地支
    pub branch: String,
    /// 藏干(主气在前)
    pub hidden: String,
}

/// 五行八字推算结果(WuxingInfo)
#[derive(Debug, Serialize)]
pub struct WuxingInfo {
    pub pillars: Vec<FourPillarInfo>,
    pub counts: WuxingCounts,
    pub canggan: Vec<CangganItem>,
    pub day_master: String,
    pub strength: String,
    pub favorable: Vec<String>,
    pub summary: String,
}

/// 星座推算结果(ConstellationInfo)
#[derive(Debug, Serialize)]
pub struct ConstellationInfo {
    pub name: String,
    pub date_range: String,
    pub element: String,
    pub traits: String,
    pub summary: String,
}

/// 生肖推算结果(ZodiacInfo)
#[derive(Debug, Serialize)]
pub struct ZodiacInfo {
    pub name: String,
    pub year_ganzhi: String,
    pub favorable_chars: String,
    pub summary: String,
}

/// 塔罗牌推算结果(TarotInfo)
#[derive(Debug, Serialize)]
pub struct TarotInfo {
    /// 生命灵数(1-22)
    pub number: i32,
    pub card: String,
    pub meaning: String,
    pub summary: String,
}

/// 姓氏三才五格基准(SancaiBaseInfo)
#[derive(Debug, Serialize)]
pub struct SancaiBaseInfo {
    /// 姓氏各字康熙笔画(动态键, 按姓氏字符序输出)
    pub surname_strokes: std::collections::BTreeMap<String, i32>,
    /// 笔画为估计值的字
    pub estimated_chars: Vec<String>,
    /// 天格(单姓=笔画+1, 复姓=笔画和)
    pub tian_ge: i32,
    pub note: String,
}

/// 佛教本命佛推算结果(BuddhismInfo)
#[derive(Debug, Serialize)]
pub struct BuddhismInfo {
    pub zodiac: String,
    pub buddha: String,
    pub meaning: String,
    pub hint_chars: String,
    pub summary: String,
}

/// 道教本命太岁推算结果(TaoismInfo)
#[derive(Debug, Serialize)]
pub struct TaoismInfo {
    pub year_ganzhi: String,
    pub taishi: String,
    pub meaning: String,
    pub hint_chars: String,
    pub summary: String,
}

/// 基督圣经意象推算结果(ChristianInfo)
#[derive(Debug, Serialize)]
pub struct ChristianInfo {
    pub season: String,
    pub theme: String,
    pub verse: String,
    pub hint_chars: String,
    pub summary: String,
}

/// 参考体系推算结果(ReferenceCalculateResult, 按选择返回对应子对象, 未选为 null)
#[derive(Debug, Default, Serialize)]
pub struct ReferenceCalculateResult {
    pub wuxing: Option<WuxingInfo>,
    pub constellation: Option<ConstellationInfo>,
    pub zodiac: Option<ZodiacInfo>,
    pub tarot: Option<TarotInfo>,
    pub sancai: Option<SancaiBaseInfo>,
    pub buddhism: Option<BuddhismInfo>,
    pub taoism: Option<TaoismInfo>,
    pub christian: Option<ChristianInfo>,
}
