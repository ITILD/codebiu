//! 分页与无限滚动(对齐 Python common/utils/db/schema/pagination.py)

use serde::{Deserialize, Serialize};

/// 分页查询参数(query 注入, 约束与 Python 字段声明一致)
#[derive(Debug, Clone, Deserialize)]
pub struct PaginationParams {
    /// 页码(从1开始)
    #[serde(default = "default_page")]
    pub page: i64,
    /// 每页条数(1~500)
    #[serde(default = "default_size")]
    pub size: i64,
}

fn default_page() -> i64 {
    1
}

fn default_size() -> i64 {
    10
}

impl Default for PaginationParams {
    fn default() -> Self {
        Self { page: default_page(), size: default_size() }
    }
}

impl PaginationParams {
    /// 分页偏移量
    pub fn offset(&self) -> u64 {
        ((self.page - 1) * self.size).max(0) as u64
    }

    /// 每页最大记录数
    pub fn limit(&self) -> u64 {
        self.size.max(0) as u64
    }

    /// 参数范围校验(违反时构造 422, loc 指向 query 字段)
    pub fn validate(&self) -> Result<(), crate::utils::error::AppError> {
        if self.page < 1 {
            return Err(crate::utils::error::validation(
                &["query", "page"],
                "Input should be greater than or equal to 1",
            ));
        }
        if self.size < 1 || self.size > 500 {
            return Err(crate::utils::error::validation(
                &["query", "size"],
                "Input should be between 1 and 500",
            ));
        }
        Ok(())
    }
}

/// 分页响应结构(字段与 Python PaginationResponse 一致)
#[derive(Debug, Clone, Serialize)]
pub struct PaginationResponse<T> {
    pub items: Vec<T>,
    pub total: i64,
    pub page: i64,
    pub size: i64,
    pub pages: i64,
}

impl<T> PaginationResponse<T> {
    /// 根据查询结果与分页参数构建响应(总页数向下取整)
    pub fn create(items: Vec<T>, total: i64, pagination: &PaginationParams) -> Self {
        Self {
            items,
            total,
            page: pagination.page,
            size: pagination.size,
            pages: (total + pagination.size - 1) / pagination.size,
        }
    }
}

/// 滚动方向(UP 升序: 获取更新更晚更大的数据)
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ScrollDirection {
    #[default]
    Up,
    Down,
}

/// 无限滚动查询参数
#[derive(Debug, Clone, Deserialize)]
pub struct InfiniteScrollParams {
    /// 客户端最后获取的记录ID
    #[serde(default)]
    pub last_id: Option<String>,
    /// 每次加载的数量
    #[serde(default = "default_scroll_limit")]
    pub limit: i64,
    /// 滚动方向
    #[serde(default)]
    pub direction: ScrollDirection,
    /// 排序字段(默认创建时间)
    #[serde(default = "default_sort_by")]
    pub sort_by: String,
}

fn default_scroll_limit() -> i64 {
    10
}

fn default_sort_by() -> String {
    "created_at".to_string()
}

impl Default for InfiniteScrollParams {
    fn default() -> Self {
        Self {
            last_id: None,
            limit: default_scroll_limit(),
            direction: ScrollDirection::Up,
            sort_by: default_sort_by(),
        }
    }
}

/// 无限滚动响应结构
#[derive(Debug, Clone, Serialize)]
pub struct InfiniteScrollResponse<T> {
    pub items: Vec<T>,
    pub last_id: Option<String>,
    pub has_more: bool,
}

impl<T: Clone> InfiniteScrollResponse<T> {
    /// 由"多查一条(limit+1 探测)"的结果构建响应
    ///
    /// items 为原始查询结果(可能含 limit+1 条), id_of 提取记录游标ID。
    /// UP 返回最后一条(更大的值), DOWN 返回第一条(更小的值)。
    pub fn create(items: Vec<T>, limit: i64, direction: ScrollDirection, id_of: impl Fn(&T) -> String) -> Self {
        let has_more = items.len() as i64 > limit;
        let items_result: Vec<T> = if has_more {
            items.into_iter().take(limit as usize).collect()
        } else {
            items
        };
        // 空结果无游标; UP 返回最后一条(更大), DOWN 返回第一条(更小)
        let last_id = if items_result.is_empty() {
            None
        } else {
            match direction {
                ScrollDirection::Up => items_result.last().map(|t| id_of(t)),
                ScrollDirection::Down => items_result.first().map(|t| id_of(t)),
            }
        };
        Self { items: items_result, last_id, has_more }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 分页参数默认值与偏移() {
        let p = PaginationParams::default();
        assert_eq!(p.page, 1);
        assert_eq!(p.offset(), 0);
        let p2 = PaginationParams { page: 3, size: 10 };
        assert_eq!(p2.offset(), 20);
    }

    #[test]
    fn 分页响应总页数向下取整() {
        let p = PaginationParams { page: 1, size: 10 };
        let r = PaginationResponse::create(vec![0u8; 25], 25, &p);
        assert_eq!(r.pages, 3);
        let r2 = PaginationResponse::<u8>::create(vec![0u8; 21], 21, &p);
        assert_eq!(r2.pages, 3);
        let r3 = PaginationResponse::<u8>::create(vec![], 0, &p);
        assert_eq!(r3.pages, 0);
    }

    #[test]
    fn 分页参数越界校验() {
        let p = PaginationParams { page: 0, size: 10 };
        assert!(p.validate().is_err());
        let p2 = PaginationParams { page: 1, size: 501 };
        assert!(p2.validate().is_err());
        let p3 = PaginationParams { page: 1, size: 10 };
        assert!(p3.validate().is_ok());
    }

    #[test]
    fn 无限滚动_has_more探测与截断() {
        let items: Vec<String> = (0..12).map(|i| i.to_string()).collect();
        let r = InfiniteScrollResponse::create(items, 10, ScrollDirection::Up, |s| s.clone());
        assert!(r.has_more);
        assert_eq!(r.items.len(), 10);
        assert_eq!(r.last_id, Some("9".to_string()));
    }

    #[test]
    fn 无限滚动_无更多数据() {
        let items: Vec<String> = (0..5).map(|i| i.to_string()).collect();
        let r = InfiniteScrollResponse::create(items, 10, ScrollDirection::Up, |s| s.clone());
        assert!(!r.has_more);
        assert_eq!(r.last_id, Some("4".to_string()));
    }
}
