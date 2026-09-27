//! 几何要素数据访问(对齐 Python dao/feature.py)
//!
//! geometry 列以 WKT 文本读写(等价 Python WKTElement(srid=4326) 的存储语义);
//! 记录不存在时统一返回 404 文案 "未找到ID为 {id} 的几何要素"。

use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, ModelTrait, PaginatorTrait,
    QueryFilter, QueryOrder, QuerySelect, Set,
};

use common::utils::error::AppError;
use common::utils::pagination::PaginationParams;
use sea_orm::prelude::Json;
use uuid::Uuid;

use crate::do_::entity::geo_feature::{self, ActiveModel, Entity as GeoFeature};
use crate::do_::feature::{GeoFeatureCreate, GeoFeatureUpdate, now_utc};

/// 记录不存在错误(文案对齐 Python NotFoundError)
fn not_found(feature_id: &str) -> AppError {
    AppError::not_found(format!("未找到ID为 {feature_id} 的几何要素"))
}

/// 新增几何要素(几何体由 service 预转为 WKT)
///
/// :param data: 创建数据(名称/属性/样式)
/// :param user_id: 创建者用户ID
/// :param wkt: WKT 格式几何文本
/// :return: 新创建要素的ID(32 位小写 hex uuid, 对齐 Python uuid4().hex)
pub async fn add(
    db: &DatabaseConnection,
    data: &GeoFeatureCreate,
    user_id: &str,
    wkt: &str,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = ActiveModel {
        id: Set(id.clone()),
        name: Set(data.name.clone()),
        // feature_type 由 GeoJSON type 小写推导(对齐 Python data.geometry.type.lower())
        feature_type: Set(data.geometry.geo_type.to_lowercase()),
        properties: Set(data.properties.clone().map(Json::Object)),
        style: Set(data.style.clone().map(Json::Object)),
        user_id: Set(user_id.to_string()),
        geometry: Set(wkt.to_string()),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    GeoFeature::insert(am).exec(db).await?;
    Ok(id)
}

/// 删除几何要素(不存在 → 404)
pub async fn delete(db: &DatabaseConnection, feature_id: &str) -> Result<(), AppError> {
    let existing = GeoFeature::find_by_id(feature_id.to_owned()).one(db).await?;
    let Some(model) = existing else {
        return Err(not_found(feature_id));
    };
    model.delete(db).await?;
    Ok(())
}

/// 更新几何要素(仅显式传入字段生效; 不存在 → 404)
///
/// :param wkt: WKT 几何文本(None 表示不更新几何)
pub async fn update(
    db: &DatabaseConnection,
    feature_id: &str,
    data: &GeoFeatureUpdate,
    wkt: Option<String>,
) -> Result<(), AppError> {
    let existing = GeoFeature::find_by_id(feature_id.to_owned()).one(db).await?;
    let Some(model) = existing else {
        return Err(not_found(feature_id));
    };
    let mut am: ActiveModel = model.into();
    if let Some(name) = &data.name {
        am.name = Set(name.clone());
    }
    if let Some(props) = &data.properties {
        am.properties = Set(Some(Json::Object(props.clone())));
    }
    if let Some(style) = &data.style {
        am.style = Set(Some(Json::Object(style.clone())));
    }
    if let Some(wkt) = wkt {
        am.geometry = Set(wkt);
        // 几何体变更时同步 feature_type(对齐 Python: data.geometry.type.lower())
        if let Some(g) = &data.geometry {
            am.feature_type = Set(g.geo_type.to_lowercase());
        }
    }
    am.updated_at = Set(now_utc());
    am.update(db).await?;
    Ok(())
}

/// 查询单个几何要素(未找到返回 None)
pub async fn get(
    db: &DatabaseConnection,
    feature_id: &str,
) -> Result<Option<geo_feature::Model>, AppError> {
    Ok(GeoFeature::find_by_id(feature_id.to_owned()).one(db).await?)
}

/// 组装名称模糊/类型精确过滤条件(列表与计数共用)
fn filter_cond(keyword: Option<&str>, feature_type: Option<&str>) -> sea_orm::Condition {
    let mut cond = sea_orm::Condition::all();
    if let Some(kw) = keyword.filter(|k| !k.is_empty()) {
        cond = cond.add(geo_feature::Column::Name.contains(kw));
    }
    if let Some(ft) = feature_type.filter(|t| !t.is_empty()) {
        cond = cond.add(geo_feature::Column::FeatureType.eq(ft));
    }
    cond
}

/// 分页查询几何要素列表(按创建时间倒序)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    keyword: Option<&str>,
    feature_type: Option<&str>,
) -> Result<Vec<geo_feature::Model>, AppError> {
    let models = GeoFeature::find()
        .filter(filter_cond(keyword, feature_type))
        .order_by_desc(geo_feature::Column::CreatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?;
    Ok(models)
}

/// 查询全部几何要素(按创建时间倒序, 最多 2000 条)
pub async fn list_all(db: &DatabaseConnection) -> Result<Vec<geo_feature::Model>, AppError> {
    let models = GeoFeature::find()
        .order_by_desc(geo_feature::Column::CreatedAt)
        .limit(2000)
        .all(db)
        .await?;
    Ok(models)
}

/// 统计几何要素总数(与列表过滤条件保持一致)
pub async fn count(
    db: &DatabaseConnection,
    keyword: Option<&str>,
    feature_type: Option<&str>,
) -> Result<i64, AppError> {
    let total = GeoFeature::find()
        .filter(filter_cond(keyword, feature_type))
        .count(db)
        .await?;
    Ok(total as i64)
}
