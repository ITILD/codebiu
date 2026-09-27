//! 起名参考体系注册表(对齐 Python folklore.py)
//!
//! strict=true: 有经典严格计算方法, 由后端程序按出生日期精确推算
//! (五行八字/三才五格/星座/生肖/塔罗/基督季节意象/佛教本命佛/道教本命太岁)。

use serde::{Deserialize, Serialize};

/// 参考体系标识(与前端多选卡片一一对应, 对齐 Python ReferenceEnum)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Reference {
    /// 五行八字
    Wuxing,
    /// 三才五格
    Sancai,
    /// 星座
    Constellation,
    /// 生肖
    Zodiac,
    /// 塔罗牌
    Tarot,
    /// 基督
    Christian,
    /// 佛教
    Buddhism,
    /// 道教
    Taoism,
}

impl Reference {
    /// API 值(与 Python 枚举 value 一致的小写字符串)
    pub fn as_str(self) -> &'static str {
        match self {
            Reference::Wuxing => "wuxing",
            Reference::Sancai => "sancai",
            Reference::Constellation => "constellation",
            Reference::Zodiac => "zodiac",
            Reference::Tarot => "tarot",
            Reference::Christian => "christian",
            Reference::Buddhism => "buddhism",
            Reference::Taoism => "taoism",
        }
    }
}

/// 单个参考体系定义(FolkReference)
#[derive(Debug, Clone, Copy)]
pub struct FolkReference {
    pub key: Reference,
    /// 展示名
    pub label: &'static str,
    /// 前端展示图标(emoji)
    pub icon: &'static str,
    /// 一句话说明
    pub desc: &'static str,
    /// 是否有严格程序化计算
    pub strict: bool,
    /// 注入起名提示词的风格约束
    pub prompt_hint: &'static str,
}

/// 参考体系定义表(键序与 Python FOLK_REFERENCES 一致: 五行/三才/星座/生肖/塔罗/基督/佛教/道教)
pub fn folk_references() -> [FolkReference; 8] {
    [
        FolkReference {
            key: Reference::Wuxing,
            label: "五行八字",
            icon: "☯",
            desc: "生辰干支四柱推算五行强弱与喜用神",
            strict: true,
            prompt_hint: "优先选用补益喜用五行的字(偏旁、部首或字义属性行相符), 名字五行与八字喜用呼应",
        },
        FolkReference {
            key: Reference::Sancai,
            label: "三才五格",
            icon: "☰",
            desc: "康熙笔画五格数理与天人地三才配置",
            strict: true,
            prompt_hint: "兼顾五格数理为吉(人格/地格/总格尤重), 三才配置尽量相生比和",
        },
        FolkReference {
            key: Reference::Constellation,
            label: "星座",
            icon: "✦",
            desc: "公历日期严格划分十二星座与性格意象",
            strict: true,
            prompt_hint: "用字气质与星座性格特质呼应",
        },
        FolkReference {
            key: Reference::Zodiac,
            label: "生肖",
            icon: "🧧",
            desc: "按立春分界推算生肖与宜用字形",
            strict: true,
            prompt_hint: "结合生肖宜用字根(如艹、月、禾等传统喜忌)择字",
        },
        FolkReference {
            key: Reference::Tarot,
            label: "塔罗牌",
            icon: "🃏",
            desc: "生命灵数推算生命塔罗牌寓意",
            strict: true,
            prompt_hint: "名字寓意与生命塔罗牌的精神内核相合",
        },
        FolkReference {
            key: Reference::Christian,
            label: "基督",
            icon: "✝",
            desc: "按出生季节取圣经意象与祝福经文",
            strict: true,
            prompt_hint: "名字寓意呼应出生季节的圣经意象(新生/丰盛/感恩/平安), 气质温和祝福",
        },
        FolkReference {
            key: Reference::Buddhism,
            label: "佛教",
            icon: "☸",
            desc: "按生肖取本命佛与慈悲禅意用字",
            strict: true,
            prompt_hint: "结合生肖本命佛的寓意择字, 参考慈悲、智慧、清净的佛家意象(如慧、净、慈、莲、安)",
        },
        FolkReference {
            key: Reference::Taoism,
            label: "道教",
            icon: "☯",
            desc: "按年柱取本命太岁与道家意趣",
            strict: true,
            prompt_hint: "敬本命太岁纳吉迎祥, 参考道家自然清静、逍遥飘逸的意趣(如清、然、朴、云、鹤)",
        },
    ]
}

/// 参考体系目录单项(get_reference_catalog 返回结构, 字段序与 Python 一致)
#[derive(Debug, Serialize)]
pub struct ReferenceCatalogItem {
    pub key: String,
    pub label: &'static str,
    pub icon: &'static str,
    pub desc: &'static str,
    pub strict: bool,
}

/// 参考体系目录(供前端多选卡片渲染)
pub fn get_reference_catalog() -> Vec<ReferenceCatalogItem> {
    folk_references()
        .iter()
        .map(|r| ReferenceCatalogItem {
            key: r.key.as_str().to_string(),
            label: r.label,
            icon: r.icon,
            desc: r.desc,
            strict: r.strict,
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reference_enum_serde() {
        // 反序列化接受 Python 枚举小写值
        let refs: Vec<Reference> =
            serde_json::from_str(r#"["wuxing","sancai","taoism"]"#).unwrap();
        assert_eq!(refs[0], Reference::Wuxing);
        assert_eq!(refs[2], Reference::Taoism);
        // 非法值反序列化失败(与 FastAPI 422 对应)
        assert!(serde_json::from_str::<Reference>(r#""fengshui""#).is_err());
    }

    #[test]
    fn catalog_order_and_shape() {
        let catalog = get_reference_catalog();
        assert_eq!(catalog.len(), 8);
        // 键序: 五行/三才/星座/生肖/塔罗/基督/佛教/道教
        let keys: Vec<&str> = catalog.iter().map(|c| c.key.as_str()).collect();
        assert_eq!(
            keys,
            vec!["wuxing", "sancai", "constellation", "zodiac", "tarot", "christian", "buddhism", "taoism"]
        );
        assert!(catalog.iter().all(|c| c.strict));
    }
}
