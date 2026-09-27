//! module-geometry —— 几何空间模块(对齐 Python module_geometry)
//!
//! Babylon 地球场景点线面绘制数据管理, 路由挂载在 /geometry 前缀:
//! /geometry/features  几何要素 CRUD(分页/全量/详情/创建/更新/删除)
//!
//! 分层(对齐 Python 项目): controllers(薄控制器) → services(业务规则) → dao(数据库读写),
//! 请求/响应类型在 do/ 层。
//!
//! 存储说明: Python 侧依赖 PostGIS(geometry 列 + ST_AsGeoJSON);
//! Rust 侧 sqlite/postgres 均无 PostGIS, geometry 列以 WKT 文本存储,
//! GeoJSON ↔ WKT 转换在 services 层手写实现(支持 6 种几何类型)。

pub mod controllers;
pub mod dao;
pub mod perms;
pub mod services;

// 请求/响应类型层(目录与 Python do/ 对齐; do 是 Rust 保留字, 模块名用 do_)
#[path = "do/mod.rs"]
pub mod do_;

use axum::Router;
use common::runtime::AppState;
use sea_orm::ConnectionTrait;

/// 模块路由(由 app 主入口 nest 到 /geometry 前缀, 对齐 Python app.mount("/geometry", module_app))
///
/// 端点完整路径: /geometry/features(创建) /geometry/features/list /geometry/features/all
/// /geometry/features/{feature_id}(详情/更新/删除)
pub fn router() -> Router<AppState> {
    controllers::feature::router()
}

/// 模块表注册(建表注册中心; app 启动期统一建表前调用)
///
/// 仅注册 geo_feature; spatial_ref_sys 为 PostGIS 扩展自带的系统表
/// (Python 侧亦未声明该模型建表), Rust 无 PostGIS 不注册。
pub fn register_tables() {
    common::utils::tables::register("geo_feature", |s| {
        s.create_table_from_entity(do_::entity::geo_feature::Entity)
    });
}

/// 注册 geometry 域权限声明(启动期调用一次, 对齐 Python permissions.py)
pub fn register_permissions() {
    perms::register_geometry_define();
}

/// 模块启动钩子(建表后调用): 历史库兼容迁移
///
/// Python 时代 geo_feature.geometry 为 PostGIS geometry 类型, Rust 侧以 WKT 文本读写;
/// 对 postgres 库将旧列幂等迁移为 text(数据经 ST_AsText 转换保留, 零丢失)。
/// sqlite 库无此历史包袱, 直接跳过。
pub async fn init_hooks(state: &AppState) {
    let db = &state.db;
    if db.get_database_backend() != sea_orm::DatabaseBackend::Postgres {
        return;
    }
    // 查询列当前真实类型(自定义类型 data_type 为 USER-DEFINED, 真名在 udt_name; 已是 text 则跳过, 幂等)
    let check = sea_orm::Statement::from_string(
        db.get_database_backend(),
        "SELECT data_type, udt_name FROM information_schema.columns \
         WHERE table_name = 'geo_feature' AND column_name = 'geometry'"
            .to_string(),
    );
    match db.query_one(check).await {
        Ok(Some(row)) => {
            let ty: String = row.try_get("", "udt_name").unwrap_or_default();
            tracing::info!("geo_feature.geometry 列类型检查: udt_name={ty}");
            if ty == "geometry" {
                // ALTER TYPE 需重建列上索引, text 无 gist 操作符类 → 先删除 geometry 相关空间索引
                let idx_q = sea_orm::Statement::from_string(
                    db.get_database_backend(),
                    "SELECT i.relname AS index_name FROM pg_index x \
                     JOIN pg_class c ON c.oid = x.indrelid \
                     JOIN pg_class i ON i.oid = x.indexrelid \
                     JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'geometry' \
                     WHERE a.attnum = ANY(x.indkey) AND c.relname = 'geo_feature'"
                        .to_string(),
                );
                if let Ok(rows) = db.query_all(idx_q).await {
                    for row in rows {
                        if let Ok(name) = row.try_get::<String>("", "index_name") {
                            let drop = sea_orm::Statement::from_string(
                                db.get_database_backend(),
                                format!("DROP INDEX IF EXISTS \"{name}\""),
                            );
                            match db.execute(drop).await {
                                Ok(_) => tracing::info!("已删除空间索引 {name}(geometry 列迁移前置)"),
                                Err(e) => tracing::warn!("删除空间索引 {name} 失败: {e}"),
                            }
                        }
                    }
                }
                let alter = sea_orm::Statement::from_string(
                    db.get_database_backend(),
                    "ALTER TABLE geo_feature \
                     ALTER COLUMN geometry TYPE text USING ST_AsText(geometry)"
                        .to_string(),
                );
                match db.execute(alter).await {
                    Ok(_) => tracing::info!("geo_feature.geometry 列已迁移为 WKT 文本(历史 PostGIS 库兼容)"),
                    Err(e) => tracing::warn!("geo_feature.geometry 列迁移失败: {e}"),
                }
            }
        }
        // 表不存在(将由注册中心建表, 新表列即 text)
        Ok(None) => {}
        Err(e) => tracing::warn!("geo_feature.geometry 列类型检查失败: {e}"),
    }
}
