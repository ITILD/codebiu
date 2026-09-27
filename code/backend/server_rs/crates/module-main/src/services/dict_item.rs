//! 字典项服务(对齐 Python module_main/service/dict_item.py): 分页/滚动响应组装

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};
use crate::do_::entity::dict_item;

use crate::dao;
use crate::do_::dict_item::{DictItemCreate, DictItemUpdate};

/// 新增字典项(返回新ID)
pub async fn add(db: &DatabaseConnection, data: DictItemCreate) -> Result<String, AppError> {
    dao::dict_item::add(db, data).await
}

/// 按ID删除字典项(不存在 404)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    dao::dict_item::delete(db, id).await
}

/// 按ID部分更新字典项(仅显式传入的字段生效; 不存在 404)
pub async fn update(db: &DatabaseConnection, id: &str, data: DictItemUpdate) -> Result<(), AppError> {
    dao::dict_item::update(db, id, data).await
}

/// 查询单个字典项
pub async fn get(db: &DatabaseConnection, id: &str) -> Option<dict_item::Model> {
    dao::dict_item::get(db, id).await
}

/// 根据字典项编码全局查询(不限类型)
pub async fn get_by_code(db: &DatabaseConnection, item_code: &str) -> Option<dict_item::Model> {
    dao::dict_item::get_by_code(db, item_code).await
}

/// 根据字典类型编码查询全部字典项(类型不存在返回空列表)
pub async fn list_by_dict_type(
    db: &DatabaseConnection,
    type_code: &str,
) -> Result<Vec<dict_item::Model>, AppError> {
    dao::dict_item::list_by_dict_type(db, type_code).await
}

/// 分页查询字典项列表(无过滤; total 为全表总数)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<dict_item::Model>, AppError> {
    let items = dao::dict_item::list_paged_items(db, pagination).await?;
    let total = dao::dict_item::count(db).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 无限滚动查询字典项(UP: 取更新更晚更大的数据)
pub async fn get_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<InfiniteScrollResponse<dict_item::Model>, AppError> {
    let items = dao::dict_item::scroll_items(db, params).await?;
    Ok(InfiniteScrollResponse::create(items, params.limit, params.direction, |m| m.id.clone()))
}

/// 根据字典类型编码统计字典项数量(类型不存在返回 0)
pub async fn count_by_dict_type(
    db: &DatabaseConnection,
    type_code: &str,
) -> Result<i64, AppError> {
    dao::dict_item::count_by_dict_type(db, type_code).await
}
