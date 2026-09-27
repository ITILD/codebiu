//! 字典类型服务(对齐 Python module_main/service/dict_type.py): 分页/滚动响应组装

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};
use crate::do_::entity::dict_type;

use crate::dao;
use crate::do_::dict_type::{DictTypeCreate, DictTypeUpdate};

/// 新增字典类型(返回新ID)
pub async fn add(db: &DatabaseConnection, data: DictTypeCreate) -> Result<String, AppError> {
    dao::dict_type::add(db, data).await
}

/// 按ID删除字典类型(不存在 404)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    dao::dict_type::delete(db, id).await
}

/// 按ID部分更新字典类型(仅显式传入的字段生效; 不存在 404)
pub async fn update(db: &DatabaseConnection, id: &str, data: DictTypeUpdate) -> Result<(), AppError> {
    dao::dict_type::update(db, id, data).await
}

/// 查询单个字典类型
pub async fn get(db: &DatabaseConnection, id: &str) -> Option<dict_type::Model> {
    dao::dict_type::get(db, id).await
}

/// 根据字典类型编码查询
pub async fn get_by_code(db: &DatabaseConnection, type_code: &str) -> Option<dict_type::Model> {
    dao::dict_type::get_by_code(db, type_code).await
}

/// 分页查询字典类型列表(类型名称/编码模糊, 状态精确)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<&str>,
    is_active: Option<bool>,
) -> Result<PaginationResponse<dict_type::Model>, AppError> {
    let items = dao::dict_type::list_paged_items(db, pagination, keyword, is_active).await?;
    let total = dao::dict_type::count(db, keyword, is_active).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 无限滚动查询(UP: 取更新更晚更大的数据)
pub async fn get_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<InfiniteScrollResponse<dict_type::Model>, AppError> {
    let items = dao::dict_type::scroll_items(db, params).await?;
    Ok(InfiniteScrollResponse::create(items, params.limit, params.direction, |m| m.id.clone()))
}
