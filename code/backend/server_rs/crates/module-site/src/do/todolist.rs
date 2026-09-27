//! 备忘数据对象(对齐 Python module_site/do/todolist.py)

use chrono::{DateTime, FixedOffset};
use serde::{Deserialize, Serialize};

/// 备忘状态: 待办 / 完成 / 暂停
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TodoStatus {
    #[default]
    Todo,
    Done,
    Pause,
}

impl TodoStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            TodoStatus::Todo => "todo",
            TodoStatus::Done => "done",
            TodoStatus::Pause => "pause",
        }
    }
}

/// 创建备忘请求(TodolistCreate, 归属由令牌解析)
#[derive(Debug, Deserialize)]
pub struct TodolistCreate {
    #[serde(default)]
    pub name: Option<String>,
    /// 备忘全文内容(默认空串)
    #[serde(default)]
    pub value: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    /// 备忘时间(日历展示依据, 默认当前时间)
    #[serde(default)]
    pub start_at: Option<DateTime<FixedOffset>>,
    #[serde(default)]
    pub end_at: Option<DateTime<FixedOffset>>,
    /// 备忘状态(默认 todo)
    #[serde(default)]
    pub status: Option<TodoStatus>,
}

/// 更新备忘请求(TodolistUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct TodolistUpdate {
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub value: Option<String>,
    /// 描述(可空: 传 null 置 NULL)
    #[serde(default)]
    pub description: Option<Option<String>>,
    #[serde(default)]
    pub start_at: Option<DateTime<FixedOffset>>,
    /// 截止时间(可空: 传 null 置 NULL)
    #[serde(default)]
    pub end_at: Option<Option<DateTime<FixedOffset>>>,
    #[serde(default)]
    pub status: Option<TodoStatus>,
}
