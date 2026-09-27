//! 分块模型(对齐 Python utils/file_parase/do/chunk.py)
//!
//! 文档解析的统一输出单元: 内容 + 内容类型 + 位置 + 非标元数据。

use serde::Serialize;
use serde_json::{Map, Value};

/// 内容类型枚举(对齐 Python ContentType; 响应序列化为 snake_case 字符串)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ContentType {
    /// 普通文本
    Text,
    /// 标题
    Title,
    /// 文件链接
    Image,
    /// 图片描述内容
    ImageContent,
    Audio,
    Video,
    /// 表格 sheet 页
    TableSheet,
    /// 完整表格(小于等于1000字)
    Table,
    /// 大表格表头
    TableHeader,
    /// 大表格内容
    TableContent,
    /// Python/Java 等源代码(代码块由专用解析器按符号边界生成)
    Code,
}

/// 位置模型(对齐 Python Position; 全字段序列化, None 输出 null)
#[derive(Debug, Clone, Default, Serialize)]
pub struct Position {
    /// 页码
    pub page: Option<i64>,
    /// 文本起始结束的行列数组[start_row,start_col,end_row,end_col]
    pub text_range: Option<Vec<i64>>,
    /// 音视频时间[start_time,end_time]
    pub time_range: Option<Vec<f64>>,
    /// PDF/图片边界框[l,t,r,b]
    pub bbox: Option<Vec<f64>>,
    /// 语义标题级别(1=h1,2=h2...);标题元素与sheet页有值,正文为None
    pub heading_level: Option<i64>,
}

/// 分块模型(对齐 Python Chunk)
#[derive(Debug, Clone, Serialize)]
pub struct Chunk {
    /// 文本内容
    pub content: Option<String>,
    /// 内容类型
    pub content_type: ContentType,
    /// 位置
    pub position: Position,
    /// 非标元数据
    pub metadata: Option<Map<String, Value>>,
}

impl Chunk {
    /// 构建纯文本分块(内容类型 Text, 位置默认全空)
    pub fn text(content: impl Into<String>) -> Self {
        Self {
            content: Some(content.into()),
            content_type: ContentType::Text,
            position: Position::default(),
            metadata: None,
        }
    }

    /// 构建代码分块(内容类型 Code, 位置带行列范围与符号元数据)
    pub fn code(
        content: impl Into<String>,
        start_line: i64,
        end_line: i64,
        metadata: Map<String, Value>,
    ) -> Self {
        Self {
            content: Some(content.into()),
            content_type: ContentType::Code,
            position: Position { text_range: Some(vec![start_line, 0, end_line, 0]), ..Default::default() },
            metadata: Some(metadata),
        }
    }
}
