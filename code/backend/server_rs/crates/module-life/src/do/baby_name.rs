//! 宝宝名字数据对象(对齐 Python module_life/do/baby_name.py 的 baby_name 表模型)

use chrono::{DateTime, FixedOffset};
use serde::{Deserialize, Serialize};

// ############################# 字段枚举 #############################

/// 性别(GenderEnum: boy/girl/unknown)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Gender {
    Boy,
    Girl,
    Unknown,
}

impl Gender {
    /// API 输出值(与 Python 枚举 value 一致的小写)
    pub fn as_str(self) -> &'static str {
        match self {
            Gender::Boy => "boy",
            Gender::Girl => "girl",
            Gender::Unknown => "unknown",
        }
    }

    /// 数据库枚举值(sea-orm codegen 大写)
    pub fn db_value(self) -> &'static str {
        match self {
            Gender::Boy => "BOY",
            Gender::Girl => "GIRL",
            Gender::Unknown => "UNKNOWN",
        }
    }

    /// 转实体枚举(ActiveModel 写库用)
    pub fn to_entity(self) -> crate::do_::entity::sea_orm_active_enums::Genderenum {
        match self {
            Gender::Boy => crate::do_::entity::sea_orm_active_enums::Genderenum::Boy,
            Gender::Girl => crate::do_::entity::sea_orm_active_enums::Genderenum::Girl,
            Gender::Unknown => crate::do_::entity::sea_orm_active_enums::Genderenum::Unknown,
        }
    }
}

impl From<crate::do_::entity::sea_orm_active_enums::Genderenum> for Gender {
    fn from(v: crate::do_::entity::sea_orm_active_enums::Genderenum) -> Self {
        match v {
            crate::do_::entity::sea_orm_active_enums::Genderenum::Boy => Gender::Boy,
            crate::do_::entity::sea_orm_active_enums::Genderenum::Girl => Gender::Girl,
            crate::do_::entity::sea_orm_active_enums::Genderenum::Unknown => Gender::Unknown,
        }
    }
}

/// 名字风格(NameStyleEnum: traditional/modern/literary/simple/unique)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NameStyle {
    Traditional,
    Modern,
    Literary,
    Simple,
    Unique,
}

impl NameStyle {
    /// API 输出值(与 Python 枚举 value 一致的小写)
    pub fn as_str(self) -> &'static str {
        match self {
            NameStyle::Traditional => "traditional",
            NameStyle::Modern => "modern",
            NameStyle::Literary => "literary",
            NameStyle::Simple => "simple",
            NameStyle::Unique => "unique",
        }
    }

    /// 数据库枚举值(sea-orm codegen 大写)
    pub fn db_value(self) -> &'static str {
        match self {
            NameStyle::Traditional => "TRADITIONAL",
            NameStyle::Modern => "MODERN",
            NameStyle::Literary => "LITERARY",
            NameStyle::Simple => "SIMPLE",
            NameStyle::Unique => "UNIQUE",
        }
    }

    /// 转实体枚举(ActiveModel 写库用)
    pub fn to_entity(self) -> crate::do_::entity::sea_orm_active_enums::Namestyleenum {
        match self {
            NameStyle::Traditional => crate::do_::entity::sea_orm_active_enums::Namestyleenum::Traditional,
            NameStyle::Modern => crate::do_::entity::sea_orm_active_enums::Namestyleenum::Modern,
            NameStyle::Literary => crate::do_::entity::sea_orm_active_enums::Namestyleenum::Literary,
            NameStyle::Simple => crate::do_::entity::sea_orm_active_enums::Namestyleenum::Simple,
            NameStyle::Unique => crate::do_::entity::sea_orm_active_enums::Namestyleenum::Unique,
        }
    }
}

impl From<crate::do_::entity::sea_orm_active_enums::Namestyleenum> for NameStyle {
    fn from(v: crate::do_::entity::sea_orm_active_enums::Namestyleenum) -> Self {
        match v {
            crate::do_::entity::sea_orm_active_enums::Namestyleenum::Traditional => NameStyle::Traditional,
            crate::do_::entity::sea_orm_active_enums::Namestyleenum::Modern => NameStyle::Modern,
            crate::do_::entity::sea_orm_active_enums::Namestyleenum::Literary => NameStyle::Literary,
            crate::do_::entity::sea_orm_active_enums::Namestyleenum::Simple => NameStyle::Simple,
            crate::do_::entity::sea_orm_active_enums::Namestyleenum::Unique => NameStyle::Unique,
        }
    }
}

// ############################# CRUD 请求/响应 #############################

/// 创建宝宝名字请求(BabyNameCreate; 未传字段取 Python 模型默认值)
#[derive(Debug, Deserialize)]
pub struct BabyNameCreate {
    /// 宝宝名字(1-10 个字符)
    pub name: String,
    pub gender: Gender,
    pub style: NameStyle,
    #[serde(default)]
    pub meaning: Option<String>,
    #[serde(default)]
    pub pinyin: Option<String>,
    #[serde(default)]
    pub stroke_count: Option<i32>,
    /// 是否吉利(默认 true)
    #[serde(default)]
    pub is_lucky: Option<bool>,
    /// 流行度评分(默认 0)
    #[serde(default)]
    pub popularity: Option<i32>,
    #[serde(default)]
    pub tags: Option<String>,
    #[serde(default)]
    pub source: Option<String>,
    /// 是否激活(默认 true)
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 更新宝宝名字请求(BabyNameUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct BabyNameUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub gender: Option<Gender>,
    #[serde(default)]
    pub style: Option<NameStyle>,
    /// 名字含义(可空: 传 null 置 NULL)
    #[serde(default)]
    pub meaning: Option<Option<String>>,
    /// 拼音(可空: 传 null 置 NULL)
    #[serde(default)]
    pub pinyin: Option<Option<String>>,
    /// 笔画数(可空: 传 null 置 NULL)
    #[serde(default)]
    pub stroke_count: Option<Option<i32>>,
    #[serde(default)]
    pub is_lucky: Option<bool>,
    #[serde(default)]
    pub popularity: Option<i32>,
    /// 标签(可空: 传 null 置 NULL)
    #[serde(default)]
    pub tags: Option<Option<String>>,
    /// 来源(可空: 传 null 置 NULL)
    #[serde(default)]
    pub source: Option<Option<String>>,
    #[serde(default)]
    pub is_active: Option<bool>,
}

/// 批量删除宝宝名字请求(BabyNameBatchDelete)
#[derive(Debug, Deserialize)]
pub struct BabyNameBatchDelete {
    /// 要删除的名字ID列表
    pub ids: Vec<String>,
}

/// 宝宝名字响应(字段与 Python BabyName 模型一致; gender/style 输出小写)
#[derive(Debug, Clone, Serialize)]
pub struct BabyNameOut {
    pub name: String,
    pub gender: String,
    pub style: String,
    pub meaning: Option<String>,
    pub pinyin: Option<String>,
    pub stroke_count: Option<i32>,
    pub is_lucky: Option<bool>,
    pub popularity: i32,
    pub tags: Option<String>,
    pub source: Option<String>,
    pub is_active: Option<bool>,
    pub id: String,
    pub created_at: Option<DateTime<FixedOffset>>,
    pub updated_at: DateTime<FixedOffset>,
}

impl From<crate::do_::entity::baby_name::Model> for BabyNameOut {
    fn from(m: crate::do_::entity::baby_name::Model) -> Self {
        Self {
            name: m.name,
            gender: Gender::from(m.gender).as_str().to_string(),
            style: NameStyle::from(m.style).as_str().to_string(),
            meaning: m.meaning,
            pinyin: m.pinyin,
            stroke_count: m.stroke_count,
            is_lucky: m.is_lucky,
            popularity: m.popularity,
            tags: m.tags,
            source: m.source,
            is_active: m.is_active,
            id: m.id,
            created_at: m.created_at,
            updated_at: m.updated_at,
        }
    }
}
