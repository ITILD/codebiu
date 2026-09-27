//! 几何要素请求/响应模型(对齐 Python do/feature.py 的非表模型部分)
//!
//! geometry 字段以 GeoJSON 形状收发(type + coordinates), WKT 转换在 services 层完成。

use serde::{Deserialize, Serialize};
use serde_json::Map;

/// GeoJSON 几何体(对齐 Python GeoJSONGeometry)
///
/// coordinates 结构:
/// - Point            -> [lon, lat]
/// - LineString       -> [[lon, lat], ...]
/// - Polygon          -> [[[lon, lat], ...], ...](外环在前, 首尾自动闭合)
/// - MultiPoint       -> [[lon, lat], ...]
/// - MultiLineString  -> [[[lon, lat], ...], ...]
/// - MultiPolygon     -> [[[[lon, lat], ...], ...], ...]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeoJsonGeometry {
    /// 几何类型(Point/LineString/Polygon/MultiPoint/MultiLineString/MultiPolygon)
    #[serde(rename = "type")]
    pub geo_type: String,
    /// GeoJSON 坐标(嵌套数字数组)
    pub coordinates: serde_json::Value,
}

/// 创建几何要素请求(对齐 Python GeoFeatureCreate)
#[derive(Debug, Deserialize)]
pub struct GeoFeatureCreate {
    /// 要素名称
    pub name: String,
    /// GeoJSON 几何体
    pub geometry: GeoJsonGeometry,
    /// GeoJSON properties 扩展属性
    #[serde(default)]
    pub properties: Option<Map<String, serde_json::Value>>,
    /// 渲染样式 JSON(由前端定义结构)
    #[serde(default)]
    pub style: Option<Map<String, serde_json::Value>>,
}

/// 更新几何要素请求(字段全部可选, 对齐 Python GeoFeatureUpdate)
#[derive(Debug, Deserialize)]
pub struct GeoFeatureUpdate {
    /// 要素名称
    #[serde(default)]
    pub name: Option<String>,
    /// GeoJSON 几何体
    #[serde(default)]
    pub geometry: Option<GeoJsonGeometry>,
    /// GeoJSON properties 扩展属性
    #[serde(default)]
    pub properties: Option<Map<String, serde_json::Value>>,
    /// 渲染样式 JSON
    #[serde(default)]
    pub style: Option<Map<String, serde_json::Value>>,
}

/// 几何要素响应(对齐 Python GeoFeatureResponse; geometry 已转为 GeoJSON)
#[derive(Debug, Serialize)]
pub struct GeoFeatureResponse {
    pub id: String,
    pub name: String,
    pub feature_type: String,
    pub properties: Option<Map<String, serde_json::Value>>,
    pub style: Option<Map<String, serde_json::Value>>,
    pub user_id: String,
    pub geometry: Option<GeoJsonGeometry>,
    pub created_at: chrono::DateTime<chrono::FixedOffset>,
    pub updated_at: chrono::DateTime<chrono::FixedOffset>,
}

/// 当前时间(UTC, 带时区偏移; 对齐 Python datetime.now(timezone.utc))
pub fn now_utc() -> chrono::DateTime<chrono::FixedOffset> {
    chrono::Utc::now().fixed_offset()
}
