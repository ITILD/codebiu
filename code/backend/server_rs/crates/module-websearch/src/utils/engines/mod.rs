//! 搜索引擎工厂(注册表)
//!
//! 新增引擎步骤:
//!     1. 在 do_.websearch.Engine 枚举追加引擎标识
//!     2. 在 engines 目录新建引擎文件,实现 utils.SearchEngine trait
//!     3. 在下方 ENGINE 列表追加引擎实例构造

pub mod duckduckgo;
pub mod firecrawl;
pub mod tavily;

use std::sync::Arc;

use crate::utils::SearchEngine;

/// 引擎注册表(顺序即 /engines 接口返回顺序)
pub fn engine_registry() -> Vec<Arc<dyn SearchEngine>> {
    vec![
        Arc::new(duckduckgo::DuckDuckGoEngine),
        Arc::new(tavily::TavilyEngine),
        Arc::new(firecrawl::FirecrawlEngine),
    ]
}
