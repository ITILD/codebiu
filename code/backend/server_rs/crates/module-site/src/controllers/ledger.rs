//! 记账控制器(对齐 Python module_site/controller/ledger.py)
//!
//! 路由前缀 /site/ledger/records: 收支记录 CRUD + 统计(概览/饼图/趋势)。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;

use crate::do_::entity::ledger_record;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::do_::ledger::{LedgerRecordCreate, LedgerRecordUpdate, LedgerStats};
use crate::services;

/// site:ledger 资源权限校验
async fn require_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "site", "ledger", act).await
}

/// POST "" —— 记一笔(201; 返回记录ID)
pub async fn create_ledger_record(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<LedgerRecordCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_perm(&actor, "create").await?;
    let id = services::ledger::add(&state.db, data, &actor.id).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /stats 查询参数
#[derive(Debug, Deserialize)]
pub struct StatsQuery {
    /// 统计周期 YYYY-MM(月度) 或 YYYY(年度)
    pub month: String,
}

/// 校验统计周期格式(对齐 Python Query pattern: ^\d{4}(-(0[1-9]|1[0-2]))?$)
fn validate_month(month: &str) -> Result<(), AppError> {
    let ok = match month.len() {
        4 => month.bytes().all(|b| b.is_ascii_digit()),
        7 => {
            month.as_bytes()[4] == b'-'
                && month[..4].bytes().all(|b| b.is_ascii_digit())
                && matches!(&month[5..], "01" | "02" | "03" | "04" | "05" | "06" | "07" | "08" | "09" | "10" | "11" | "12")
        }
        _ => false,
    };
    if ok {
        Ok(())
    } else {
        Err(AppError::validation(
            &["query", "month"],
            r#"String should match pattern '^\d{4}(-(0[1-9]|1[0-2]))?$'"#,
        ))
    }
}

/// GET /stats —— 记账统计(概览+饼图+趋势, 支持月/年)
pub async fn get_ledger_stats(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(query): AppQuery<StatsQuery>,
) -> Result<Json<LedgerStats>, AppError> {
    require_perm(&actor, "read").await?;
    validate_month(&query.month)?;
    let stats = services::ledger::stats(&state.db, &actor.id, query.month).await?;
    Ok(Json(stats))
}

/// GET /list 查询参数
#[derive(Debug, Deserialize)]
pub struct MyListQuery {
    /// 按月过滤 YYYY-MM
    #[serde(default)]
    pub month: Option<String>,
    /// 收支方向过滤(income/expense)
    #[serde(default)]
    pub flow_type: Option<String>,
    /// 分类模糊搜索(最长 50)
    #[serde(default)]
    pub category: Option<String>,
}

/// GET /list —— 分页查询本人记账记录(按记账日期倒序)
pub async fn list_ledger_records(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(pagination): AppQuery<PaginationParams>,
    AppQuery(query): AppQuery<MyListQuery>,
) -> Result<Json<PaginationResponse<ledger_record::Model>>, AppError> {
    require_perm(&actor, "read").await?;
    pagination.validate()?;
    let page = services::ledger::list_mine(
        &state.db,
        &pagination,
        &actor.id,
        query.month,
        query.flow_type,
        query.category,
    )
    .await?;
    Ok(Json(page))
}

/// GET /{record_id} —— 获取单条记账记录(仅本人可见, 不存在 404)
pub async fn get_ledger_record(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(record_id): Path<String>,
) -> Result<Json<ledger_record::Model>, AppError> {
    require_perm(&actor, "read").await?;
    services::ledger::get(&state.db, &record_id, &actor.id)
        .await?
        .map(Json)
        .ok_or_else(|| AppError::not_found("记账记录不存在"))
}

/// DELETE /{record_id} —— 删除本人记账记录(204; 不存在或不属于当前用户 404)
pub async fn delete_ledger_record(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(record_id): Path<String>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "delete").await?;
    services::ledger::delete(&state.db, &record_id, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /{record_id} —— 更新本人记账记录(204; 仅显式传入的字段生效; 不存在 404)
pub async fn update_ledger_record(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(record_id): Path<String>,
    AppJson(data): AppJson<LedgerRecordUpdate>,
) -> Result<StatusCode, AppError> {
    require_perm(&actor, "update").await?;
    services::ledger::update(&state.db, &record_id, data, &actor.id).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// 记账子路由(nest 到 /site/ledger/records 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/", post(create_ledger_record))
        .route("/stats", get(get_ledger_stats))
        .route("/list", get(list_ledger_records))
        .route(
            "/{record_id}",
            get(get_ledger_record)
                .delete(delete_ledger_record)
                .put(update_ledger_record),
        )
}
