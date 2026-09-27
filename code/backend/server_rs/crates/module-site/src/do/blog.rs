//! 博客文章数据对象(对齐 Python module_site/do/blog.py)

use serde::Deserialize;

/// 发布来源: markdown 在线编辑 / url 关联外链
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PostSource {
    #[default]
    Markdown,
    Url,
}

impl PostSource {
    pub fn as_str(self) -> &'static str {
        match self {
            PostSource::Markdown => "markdown",
            PostSource::Url => "url",
        }
    }
}

/// 发布状态: 草稿 / 已发布
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PostStatus {
    Draft,
    Published,
}

impl PostStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            PostStatus::Draft => "draft",
            PostStatus::Published => "published",
        }
    }
}

/// 创建博客文章请求(BlogPostCreate)
#[derive(Debug, Deserialize)]
pub struct BlogPostCreate {
    pub title: String,
    /// 发布来源(默认 markdown)
    #[serde(default)]
    pub source_type: Option<PostSource>,
    /// markdown 正文(source_type=url 时可空)
    #[serde(default)]
    pub content: Option<String>,
    /// 关联博客外链地址(source_type=url 时必填)
    #[serde(default)]
    pub url: Option<String>,
    #[serde(default)]
    pub category: Option<String>,
    /// 发布状态(默认 draft)
    #[serde(default)]
    pub status: Option<PostStatus>,
}

/// 更新博客文章请求(BlogPostUpdate, 全部可选仅更新传入字段)
#[derive(Debug, Default, Deserialize)]
pub struct BlogPostUpdate {
    #[serde(default)]
    pub title: Option<String>,
    #[serde(default)]
    pub source_type: Option<PostSource>,
    /// 正文(可空: 传 null 置 NULL)
    #[serde(default)]
    pub content: Option<Option<String>>,
    /// 外链(可空: 传 null 置 NULL)
    #[serde(default)]
    pub url: Option<Option<String>>,
    /// 分类(可空: 传 null 置 NULL)
    #[serde(default)]
    pub category: Option<Option<String>>,
    #[serde(default)]
    pub status: Option<PostStatus>,
}
