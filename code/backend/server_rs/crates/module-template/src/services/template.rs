//! 模板服务: 创建/分页/无限滚动/详情/删除/批量删除/更新

use sea_orm::DatabaseConnection;

use crate::do_::entity::template;

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::dao;
use crate::do_::template::{TemplateCreate, TemplateUpdate};

/// 创建模板
///
/// :return: 新建模板ID
pub async fn add(db: &DatabaseConnection, data: TemplateCreate) -> Result<String, AppError> {
    dao::template::add(db, data).await
}

/// 查询单个模板(不存在时由控制器决定 404 语义)
pub async fn get(
    db: &DatabaseConnection,
    template_id: &str,
) -> Result<Option<template::Model>, AppError> {
    dao::template::get(db, template_id).await
}

/// 无限滚动查询(游标过滤与排序在 dao 层, 此处组装响应)
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<InfiniteScrollResponse<template::Model>, AppError> {
    let items = dao::template::scroll(db, params).await?;
    Ok(InfiniteScrollResponse::create(
        items,
        params.limit,
        params.direction,
        |m| m.id.clone(),
    ))
}

/// 分页查询模板列表(total 为全表总数)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<template::Model>, AppError> {
    let total = dao::template::count_all(db).await?;
    let items = dao::template::list_paged(db, pagination).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 删除模板(不存在 404)
pub async fn delete(db: &DatabaseConnection, template_id: &str) -> Result<(), AppError> {
    dao::template::delete(db, template_id).await
}

/// 批量删除模板(不存在的ID静默跳过)
///
/// :return: 实际删除数量
pub async fn batch_delete(db: &DatabaseConnection, ids: Vec<String>) -> Result<u64, AppError> {
    dao::template::batch_delete(db, ids).await
}

/// 更新模板(仅显式传入字段生效; 不存在 404)
pub async fn update(
    db: &DatabaseConnection,
    template_id: &str,
    data: TemplateUpdate,
) -> Result<(), AppError> {
    dao::template::update(db, template_id, data).await
}
