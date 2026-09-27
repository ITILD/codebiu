//! 几何要素服务(对齐 Python service/feature.py)
//!
//! 核心: GeoJSON ↔ WKT 双向转换(手写实现, 不引入新依赖)。
//! Python 侧依赖 PostGIS(ST_GeomFromText/ST_AsGeoJSON), Rust 侧 sqlite/postgres
//! 无 PostGIS, geometry 列以 WKT 文本存储, 转换在本层完成。
//! 支持几何类型: Point/LineString/Polygon/MultiPoint/MultiLineString/MultiPolygon。

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use serde_json::Value;

use crate::dao::feature as feature_dao;
use crate::do_::entity::geo_feature;
use crate::do_::feature::{
    GeoFeatureCreate, GeoFeatureResponse, GeoFeatureUpdate, GeoJsonGeometry, now_utc,
};

/// GeoJSON 类型 → 本模块要素类型(分页过滤白名单, 对齐 Python _GEOJSON_TYPES)
const GEOJSON_TYPES: [&str; 3] = ["point", "linestring", "polygon"];

// ==================== GeoJSON → WKT ====================

/// 经纬度转字符串(整数也保留一位小数, WKT 合法; 保留 6 位小数去尾零, 对齐 Python fmt)
fn fmt_coord(value: f64) -> String {
    format!("{value:.6}").trim_end_matches('0').trim_end_matches('.').to_string()
}

/// 从 JSON 数组元素读取数值(数字直取, 字符串数字宽容解析, 对齐 Python float(pair[0])))
fn read_number(v: &Value) -> Result<f64, AppError> {
    match v {
        Value::Number(n) => n.as_f64().ok_or_else(|| coord_error()),
        Value::String(s) => s
            .trim()
            .parse::<f64>()
            .map_err(|_| coord_error()),
        _ => Err(coord_error()),
    }
}

/// 坐标结构非法错误(文案对齐 Python ValueError)
fn coord_error() -> AppError {
    AppError::business("坐标必须是 [经度, 纬度] 结构")
}

/// 单个坐标对转 WKT 坐标文本(经度 纬度)
fn coord_text(pair: &Value) -> Result<String, AppError> {
    let arr = pair.as_array().ok_or_else(coord_error)?;
    if arr.len() < 2 {
        return Err(coord_error());
    }
    Ok(format!("{} {}", fmt_coord(read_number(&arr[0])?), fmt_coord(read_number(&arr[1])?)))
}

/// 坐标点列表转 WKT 文本(逗号分隔)
fn points_text(points: &[Value]) -> Result<String, AppError> {
    let mut parts = Vec::with_capacity(points.len());
    for p in points {
        parts.push(coord_text(p)?);
    }
    Ok(parts.join(", "))
}

/// 多点/多线等嵌套坐标的通用校验(坐标必须是数组)
fn as_array<'a>(v: &'a Value, msg: &str) -> Result<&'a Vec<Value>, AppError> {
    v.as_array().ok_or_else(|| AppError::business(msg.to_string()))
}

/// GeoJSON 几何体转 WKT 文本(支持 6 种几何类型)
///
/// :param geometry: GeoJSON 几何体 {type, coordinates}
/// :return: WKT 字符串, 如 "POINT(116.4 39.9)"
/// :raises: AppError::business 类型不支持或坐标结构非法
pub fn geojson_to_wkt(geometry: &GeoJsonGeometry) -> Result<String, AppError> {
    let gtype = geometry.geo_type.to_lowercase();
    let coordinates = &geometry.coordinates;

    match gtype.as_str() {
        "point" => Ok(format!("POINT({})", coord_text(coordinates)?)),
        "multipoint" => {
            let points = as_array(coordinates, "坐标必须是 [经度, 纬度] 结构")?;
            Ok(format!("MULTIPOINT({})", points_text(points)?))
        }
        "linestring" => {
            let points = as_array(coordinates, "坐标必须是 [经度, 纬度] 结构")?;
            if points.len() < 2 {
                return Err(AppError::business("线要素至少需要 2 个顶点"));
            }
            Ok(format!("LINESTRING({})", points_text(points)?))
        }
        "multilinestring" => {
            let lines = as_array(coordinates, "坐标必须是 [经度, 纬度] 结构")?;
            let mut parts = Vec::with_capacity(lines.len());
            for line in lines {
                let points = as_array(line, "坐标必须是 [经度, 纬度] 结构")?;
                if points.len() < 2 {
                    return Err(AppError::business("线要素至少需要 2 个顶点"));
                }
                parts.push(format!("({})", points_text(points)?));
            }
            Ok(format!("MULTILINESTRING({})", parts.join(", ")))
        }
        "polygon" => Ok(format!("POLYGON({})", rings_text(coordinates)?)),
        "multipolygon" => {
            let polygons = as_array(coordinates, "坐标必须是 [经度, 纬度] 结构")?;
            let mut parts = Vec::with_capacity(polygons.len());
            for poly in polygons {
                parts.push(format!("({})", rings_text(poly)?));
            }
            Ok(format!("MULTIPOLYGON({})", parts.join(", ")))
        }
        other => Err(AppError::business(format!(
            "不支持的几何类型: {other}(仅支持 Point/LineString/Polygon/MultiPoint/MultiLineString/MultiPolygon)"
        ))),
    }
}

/// 面要素环列表转 WKT 文本(每环至少 3 点, 首尾不闭合时自动补首点, 对齐 Python polygon 分支)
fn rings_text(coordinates: &Value) -> Result<String, AppError> {
    let rings = as_array(coordinates, "面要素至少需要 1 个闭合环")?;
    if rings.is_empty() {
        return Err(AppError::business("面要素至少需要 1 个闭合环"));
    }
    let mut parts = Vec::with_capacity(rings.len());
    for ring in rings {
        let pts = as_array(ring, "面的每个环至少需要 3 个顶点")?;
        if pts.len() < 3 {
            return Err(AppError::business("面的每个环至少需要 3 个顶点"));
        }
        // 首尾不闭合时自动补首点(PostGIS 要求闭合环)
        let closed: Vec<Value>;
        let pts = if pts[0] != pts[pts.len() - 1] {
            closed = pts.iter().cloned().chain(std::iter::once(pts[0].clone())).collect();
            &closed
        } else {
            pts
        };
        parts.push(format!("({})", points_text(pts)?));
    }
    Ok(parts.join(", "))
}

// ==================== WKT → GeoJSON ====================

/// f64 转 JSON 数值(整值输出为整型, 与 ST_AsGeoJSON 的数字输出习惯一致)
fn num_json(v: f64) -> Value {
    if v.fract() == 0.0 && v.abs() < 1e15 {
        Value::from(v as i64)
    } else {
        serde_json::Number::from_f64(v).map(Value::Number).unwrap_or(Value::Null)
    }
}

/// WKT 解析器(递归下降, 支持 2D 标准 WKT)
struct WktParser<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> WktParser<'a> {
    fn new(text: &'a str) -> Self {
        Self { bytes: text.as_bytes(), pos: 0 }
    }

    fn skip_ws(&mut self) {
        while self.pos < self.bytes.len() && self.bytes[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    fn peek(&mut self) -> Option<u8> {
        self.skip_ws();
        self.bytes.get(self.pos).copied()
    }

    fn expect(&mut self, c: u8) -> Result<(), ()> {
        if self.peek() == Some(c) {
            self.pos += 1;
            Ok(())
        } else {
            Err(())
        }
    }

    /// 读取一个数字字面量(含正负号/小数/科学计数)
    fn read_number(&mut self) -> Result<f64, ()> {
        self.skip_ws();
        let start = self.pos;
        while self.pos < self.bytes.len() {
            let c = self.bytes[self.pos];
            if c.is_ascii_digit() || matches!(c, b'+' | b'-' | b'.' | b'e' | b'E') {
                self.pos += 1;
            } else {
                break;
            }
        }
        if start == self.pos {
            return Err(());
        }
        match std::str::from_utf8(&self.bytes[start..self.pos]) {
            Ok(text) => text.parse::<f64>().map_err(|_| ()),
            Err(_) => Err(()),
        }
    }

    /// 读取单个坐标点(x y [z ...]) → [x, y, ...]
    fn read_point(&mut self) -> Result<Value, ()> {
        let x = self.read_number()?;
        let y = self.read_number()?;
        let mut coords = vec![num_json(x), num_json(y)];
        // 兼容带 Z 坐标的 WKT(Z 值附加在坐标后, GeoJSON 侧同样输出)
        if self.peek().is_some_and(|c| c != b',' && c != b')') {
            coords.push(num_json(self.read_number()?));
        }
        Ok(Value::Array(coords))
    }

    /// 读取点列表(已消费 '(', 读到 ')' 为止但不消费右括号)
    fn read_point_list(&mut self) -> Result<Vec<Value>, ()> {
        let mut points = vec![self.read_point()?];
        while self.peek() == Some(b',') {
            self.pos += 1;
            points.push(self.read_point()?);
        }
        Ok(points)
    }

    /// 读取单个环(括号包裹的点列表; 兼容无内层括号的裸点序列简写)
    fn read_one_ring(&mut self) -> Result<Value, ()> {
        if self.peek() == Some(b'(') {
            self.pos += 1;
            let points = self.read_point_list()?;
            self.expect(b')')?;
            Ok(Value::Array(points))
        } else {
            // 裸点序列: 视为单环
            Ok(Value::Array(self.read_point_list()?))
        }
    }

    /// 读取环列表(每环至少 1 个; 读到右括号前停止, 不消费右括号)
    fn read_ring_list(&mut self) -> Result<Value, ()> {
        let mut rings = vec![self.read_one_ring()?];
        while self.peek() == Some(b',') {
            self.pos += 1;
            rings.push(self.read_one_ring()?);
        }
        Ok(Value::Array(rings))
    }

    /// 括号包裹的子项列表(子项可为括号包裹或裸形式, used by MULTI*)
    fn read_nested_list(
        &mut self,
        inner: impl Fn(&mut Self) -> Result<Value, ()>,
    ) -> Result<Value, ()> {
        let mut items = Vec::new();
        loop {
            if self.peek() == Some(b'(') {
                self.pos += 1;
                let v = inner(self)?;
                self.expect(b')')?;
                items.push(v);
            } else {
                items.push(inner(self)?);
            }
            if self.peek() == Some(b',') {
                self.pos += 1;
            } else {
                break;
            }
        }
        Ok(Value::Array(items))
    }
}

/// WKT 类型名转 GeoJSON 类型名(与 ST_AsGeoJSON 输出一致: 首字母大写驼峰)
fn geojson_type_name(wkt_type: &str) -> &'static str {
    match wkt_type {
        "POINT" => "Point",
        "LINESTRING" => "LineString",
        "POLYGON" => "Polygon",
        "MULTIPOINT" => "MultiPoint",
        "MULTILINESTRING" => "MultiLineString",
        "MULTIPOLYGON" => "MultiPolygon",
        _ => "Point",
    }
}

/// WKT 文本转 GeoJSON 几何体(等价 PostGIS ST_AsGeoJSON; 解析失败返回 None)
pub fn wkt_to_geojson(wkt: &str) -> Option<GeoJsonGeometry> {
    let trimmed = wkt.trim();
    // 兼容 EWKT 前缀(SRID=4326;POINT(...))
    let body = trimmed.split(';').next_back().unwrap_or(trimmed).trim();
    let open = body.find('(')?;
    let wkt_type = body[..open].trim().to_uppercase();
    let mut parser = WktParser::new(body);
    parser.pos = open;

    let coordinates = match wkt_type.as_str() {
        "POINT" => {
            parser.expect(b'(').ok()?;
            let v = parser.read_point().ok()?;
            parser.expect(b')').ok()?;
            v
        }
        "LINESTRING" => {
            parser.expect(b'(').ok()?;
            let points = parser.read_point_list().ok()?;
            parser.expect(b')').ok()?;
            Value::Array(points)
        }
        "POLYGON" => {
            parser.expect(b'(').ok()?;
            let rings = parser.read_ring_list().ok()?;
            parser.expect(b')').ok()?;
            rings
        }
        "MULTIPOINT" => {
            parser.expect(b'(').ok()?;
            let v = parser.read_nested_list(|p| p.read_point()).ok()?;
            parser.expect(b')').ok()?;
            v
        }
        // 子项为括号包裹的点列表 → 每项是一条线
        "MULTILINESTRING" => {
            parser.expect(b'(').ok()?;
            let v = parser.read_nested_list(|p| p.read_point_list().map(Value::Array)).ok()?;
            parser.expect(b')').ok()?;
            v
        }
        // 子项为括号包裹的环列表 → 每项是一个多边形
        "MULTIPOLYGON" => {
            parser.expect(b'(').ok()?;
            let v = parser.read_nested_list(|p| p.read_ring_list()).ok()?;
            parser.expect(b')').ok()?;
            v
        }
        _ => return None,
    };
    Some(GeoJsonGeometry { geo_type: geojson_type_name(&wkt_type).to_string(), coordinates })
}

// ==================== 业务方法 ====================

/// ORM 记录转响应模型(geometry WKT 文本转 GeoJSON 几何体)
fn to_response(model: geo_feature::Model) -> GeoFeatureResponse {
    let properties = model.properties.as_ref().and_then(|v| v.as_object().cloned());
    let style = model.style.as_ref().and_then(|v| v.as_object().cloned());
    GeoFeatureResponse {
        id: model.id,
        name: model.name,
        feature_type: model.feature_type,
        properties,
        style,
        user_id: model.user_id,
        geometry: wkt_to_geojson(&model.geometry),
        created_at: model.created_at.unwrap_or_else(now_utc),
        updated_at: model.updated_at,
    }
}

/// 新增几何要素(GeoJSON 几何体预转 WKT 后入库)
///
/// :return: 新创建要素ID
pub async fn add(db: &AppState, data: GeoFeatureCreate, user_id: &str) -> Result<String, AppError> {
    let wkt = geojson_to_wkt(&data.geometry)?;
    feature_dao::add(&db.db, &data, user_id, &wkt).await
}

/// 删除几何要素(不存在时 404)
pub async fn delete(db: &AppState, feature_id: &str) -> Result<(), AppError> {
    feature_dao::delete(&db.db, feature_id).await
}

/// 更新几何要素(几何体变更时重转 WKT 并同步 feature_type)
pub async fn update(
    db: &AppState,
    feature_id: &str,
    data: GeoFeatureUpdate,
) -> Result<(), AppError> {
    let wkt = match &data.geometry {
        Some(g) => Some(geojson_to_wkt(g)?),
        None => None,
    };
    feature_dao::update(&db.db, feature_id, &data, wkt).await
}

/// 获取单个几何要素(geometry 以 GeoJSON 返回; 未找到返回 None)
pub async fn get(
    db: &AppState,
    feature_id: &str,
) -> Result<Option<GeoFeatureResponse>, AppError> {
    feature_dao::get(&db.db, feature_id)
        .await?
        .map(|m| Ok(to_response(m)))
        .transpose()
}

/// 分页查询几何要素列表(支持名称模糊/类型精确过滤)
pub async fn list_paged(
    db: &AppState,
    pagination: &PaginationParams,
    keyword: Option<&str>,
    feature_type: Option<&str>,
) -> Result<PaginationResponse<GeoFeatureResponse>, AppError> {
    if let Some(ft) = feature_type {
        if !GEOJSON_TYPES.contains(&ft) {
            return Err(AppError::business(format!("无效的几何类型: {ft}")));
        }
    }
    let items = feature_dao::list_paged(&db.db, pagination, keyword, feature_type).await?;
    let total = feature_dao::count(&db.db, keyword, feature_type).await?;
    Ok(PaginationResponse::create(
        items.into_iter().map(to_response).collect(),
        total,
        pagination,
    ))
}

/// 查询全部几何要素(供地球场景一次性渲染, 最多 2000 条)
pub async fn list_all(db: &AppState) -> Result<Vec<GeoFeatureResponse>, AppError> {
    Ok(feature_dao::list_all(&db.db).await?.into_iter().map(to_response).collect())
}
