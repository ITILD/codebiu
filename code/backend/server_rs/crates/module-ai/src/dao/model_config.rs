//! 模型配置数据访问(对齐 Python module_ai/dao/model_config.py)
//!
//! 可见性口径: 管理员可见全部; 其他用户可见 公共 + 所在部门 + 本人 模型。

use sea_orm::sea_query::Expr;
use sea_orm::{
    ColumnTrait, Condition, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter, QueryOrder,
    QuerySelect,
};
use uuid::Uuid;

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};

use crate::do_::entity::model_config;
use crate::do_::model_config::ModelConfigUpdate;

/// 列表/计数共用的过滤条件构建(可见性 + 多字段过滤)
fn filter_condition(
    model: Option<&str>,
    model_type: Option<&str>,
    server_type: Option<&str>,
    scope: Option<&str>,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
    filter_user_ids: Option<&[String]>,
) -> Option<Condition> {
    let mut all = Condition::all();
    let mut has = false;
    if let Some(m) = model.filter(|s| !s.is_empty()) {
        all = all.add(model_config::Column::Model.contains(m));
        has = true;
    }
    if let Some(t) = model_type.filter(|s| !s.is_empty()) {
        all = all.add(model_config::Column::ModelType.eq(t));
        has = true;
    }
    if let Some(st) = server_type.filter(|s| !s.is_empty()) {
        all = all.add(model_config::Column::ServerType.eq(st));
        has = true;
    }
    if let Some(sc) = scope.filter(|s| !s.is_empty()) {
        all = all.add(model_config::Column::Scope.eq(sc));
        has = true;
    }
    if let Some(ids) = filter_user_ids.filter(|v| !v.is_empty()) {
        all = all.add(model_config::Column::UserId.is_in(ids.iter().cloned()));
        has = true;
    }
    if let Some(vis) = visibility_condition(user_id, dept_id, is_admin) {
        all = all.add(vis);
        has = true;
    }
    has.then_some(all)
}

/// 可见性条件: 管理员可见全部(None); 否则 公共 / 所在部门 / 本人
fn visibility_condition(
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
) -> Option<Condition> {
    if is_admin {
        return None;
    }
    let mut any = Condition::any().add(model_config::Column::Scope.eq("public"));
    if let Some(d) = dept_id.filter(|s| !s.is_empty()) {
        any = any.add(
            Condition::all()
                .add(model_config::Column::Scope.eq("dept"))
                .add(model_config::Column::DeptId.eq(d)),
        );
    }
    if let Some(u) = user_id.filter(|s| !s.is_empty()) {
        any = any.add(
            Condition::all()
                .add(model_config::Column::Scope.eq("user"))
                .add(model_config::Column::UserId.eq(u)),
        );
    }
    Some(any)
}

/// 新增模型配置记录(主键为 32 位小写 hex uuid, 与 Python uuid4().hex 一致)
///
/// :return: 新创建模型配置ID
pub async fn add(
    db: &DatabaseConnection,
    create: crate::do_::model_config::ModelConfigCreate,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    model_config::Entity::insert(create.to_active_model(id.clone()))
        .exec(db)
        .await?;
    Ok(id)
}

/// 按ID获取单个模型配置(不过滤可见性, 与 Python session.get 口径一致)
pub async fn get(
    db: &DatabaseConnection,
    id: &str,
) -> Result<Option<model_config::Model>, AppError> {
    Ok(model_config::Entity::find_by_id(id.to_owned()).one(db).await?)
}

/// 删除模型配置记录(物理删除)
///
/// :raises: AppError::not_found 记录不存在(文案对齐 Python)
pub async fn delete(db: &DatabaseConnection, id: &str) -> Result<(), AppError> {
    let res = model_config::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    if res.rows_affected == 0 {
        return Err(AppError::not_found(format!("未找到ID为 {id} 的模型配置")));
    }
    Ok(())
}

/// 部分更新模型配置(仅显式传入字段生效; 同步刷新 updated_at)
///
/// :raises: AppError::not_found 记录不存在(文案对齐 Python "模板")
pub async fn update(
    db: &DatabaseConnection,
    model_config_id: &str,
    patch: &ModelConfigUpdate,
) -> Result<(), AppError> {
    let mut stmt = model_config::Entity::update_many()
        .col_expr(
            model_config::Column::UpdatedAt,
            Expr::value(chrono::Utc::now().with_timezone(&chrono::FixedOffset::east_opt(0).expect("UTC 偏移合法"))),
        );
    if let Some(v) = &patch.model_type {
        stmt = stmt.col_expr(model_config::Column::ModelType, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.server_type {
        stmt = stmt.col_expr(model_config::Column::ServerType, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.model {
        stmt = stmt.col_expr(model_config::Column::Model, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.url {
        stmt = stmt.col_expr(model_config::Column::Url, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.api_key {
        stmt = stmt.col_expr(model_config::Column::ApiKey, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.scope {
        let text = match v {
            crate::do_::model_config::ModelScope::Public => "public",
            crate::do_::model_config::ModelScope::Dept => "dept",
            crate::do_::model_config::ModelScope::User => "user",
        };
        stmt = stmt.col_expr(model_config::Column::Scope, Expr::value(text));
        // scope 与遗留 is_public 列保持一致
        stmt = stmt.col_expr(
            model_config::Column::IsPublic,
            Expr::value(*v == crate::do_::model_config::ModelScope::Public),
        );
    }
    if patch.clear_dept_id {
        // 切换归属范围离开 dept: 显式置 NULL
        stmt = stmt.col_expr(model_config::Column::DeptId, Expr::value(Option::<String>::None));
    }
    if let Some(v) = &patch.dept_id {
        stmt = stmt.col_expr(model_config::Column::DeptId, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.is_default {
        stmt = stmt.col_expr(model_config::Column::IsDefault, Expr::value(*v));
    }
    if let Some(v) = &patch.is_active {
        stmt = stmt.col_expr(model_config::Column::IsActive, Expr::value(*v));
    }
    if let Some(v) = &patch.display_name {
        stmt = stmt.col_expr(model_config::Column::DisplayName, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.pay_in {
        stmt = stmt.col_expr(model_config::Column::PayIn, Expr::value(*v));
    }
    if let Some(v) = &patch.pay_out {
        stmt = stmt.col_expr(model_config::Column::PayOut, Expr::value(*v));
    }
    if let Some(v) = &patch.input_tokens {
        stmt = stmt.col_expr(model_config::Column::InputTokens, Expr::value(*v));
    }
    if let Some(v) = &patch.out_tokens {
        stmt = stmt.col_expr(model_config::Column::OutTokens, Expr::value(*v));
    }
    if let Some(v) = &patch.temperature {
        stmt = stmt.col_expr(model_config::Column::Temperature, Expr::value(*v));
    }
    if let Some(v) = &patch.timeout {
        stmt = stmt.col_expr(model_config::Column::Timeout, Expr::value(*v));
    }
    if let Some(v) = &patch.no_think {
        stmt = stmt.col_expr(model_config::Column::NoThink, Expr::value(*v));
    }
    if let Some(v) = &patch.extra {
        stmt = stmt.col_expr(model_config::Column::Extra, Expr::value(v.clone()));
    }
    if let Some(v) = &patch.check_valid {
        stmt = stmt.col_expr(model_config::Column::CheckValid, Expr::value(*v));
    }
    if let Some(v) = &patch.check_format {
        stmt = stmt.col_expr(model_config::Column::CheckFormat, Expr::value(*v));
    }
    if let Some(v) = &patch.checked_at {
        stmt = stmt.col_expr(model_config::Column::CheckedAt, Expr::value(*v));
    }
    if let Some(v) = &patch.check_result {
        stmt = stmt.col_expr(model_config::Column::CheckResult, Expr::value(v.clone()));
    }
    let res = stmt
        .filter(model_config::Column::Id.eq(model_config_id))
        .exec(db)
        .await?;
    if res.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {model_config_id} 的模板"
        )));
    }
    Ok(())
}

/// 获取指定类型的当前默认公共模型(同类型内唯一)
///
/// :param active_only: true 时仅返回生效记录(RAG 使用); false 时含未生效记录(seed 场景)
pub async fn get_default_by_type(
    db: &DatabaseConnection,
    model_type: &str,
    active_only: bool,
) -> Result<Option<model_config::Model>, AppError> {
    let mut select = model_config::Entity::find()
        .filter(model_config::Column::ModelType.eq(model_type))
        .filter(model_config::Column::Scope.eq("public"))
        .filter(model_config::Column::IsDefault.eq(true))
        .limit(1);
    if active_only {
        select = select.filter(model_config::Column::IsActive.eq(true));
    }
    Ok(select.one(db).await?)
}

/// 获取指定类型的最优先模型配置(语音/OCR 等按类型自动选择方案)
///
/// 优先级: 默认公共模型 > 任意公共模型 > 任意配置(按创建时间先后)
pub async fn get_first_by_type(
    db: &DatabaseConnection,
    model_type: &str,
    server_type: Option<&str>,
) -> Result<Option<model_config::Model>, AppError> {
    // 1) 优先默认公共模型
    let mut default_stmt = model_config::Entity::find()
        .filter(model_config::Column::ModelType.eq(model_type))
        .filter(model_config::Column::Scope.eq("public"))
        .filter(model_config::Column::IsDefault.eq(true))
        .order_by_asc(model_config::Column::CreatedAt)
        .limit(1);
    if let Some(st) = server_type {
        default_stmt = default_stmt.filter(model_config::Column::ServerType.eq(st));
    }
    if let Some(config) = default_stmt.one(db).await? {
        return Ok(Some(config));
    }
    // 2) 其次任意公共模型
    let mut public_stmt = model_config::Entity::find()
        .filter(model_config::Column::ModelType.eq(model_type))
        .filter(model_config::Column::Scope.eq("public"))
        .order_by_asc(model_config::Column::CreatedAt)
        .limit(1);
    if let Some(st) = server_type {
        public_stmt = public_stmt.filter(model_config::Column::ServerType.eq(st));
    }
    if let Some(config) = public_stmt.one(db).await? {
        return Ok(Some(config));
    }
    // 3) 回退: 任意归属配置
    let mut fallback = model_config::Entity::find()
        .filter(model_config::Column::ModelType.eq(model_type))
        .order_by_asc(model_config::Column::CreatedAt)
        .limit(1);
    if let Some(st) = server_type {
        fallback = fallback.filter(model_config::Column::ServerType.eq(st));
    }
    Ok(fallback.one(db).await?)
}

/// 分页获取模型配置列表(支持多字段过滤 + 可见性控制)
pub async fn list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    model: Option<&str>,
    model_type: Option<&str>,
    server_type: Option<&str>,
    scope: Option<&str>,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
    filter_user_ids: Option<&[String]>,
) -> Result<Vec<model_config::Model>, AppError> {
    let mut select = model_config::Entity::find();
    if let Some(cond) = filter_condition(
        model, model_type, server_type, scope, user_id, dept_id, is_admin, filter_user_ids,
    ) {
        select = select.filter(cond);
    }
    let items = select
        .order_by_desc(model_config::Column::UpdatedAt)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?;
    Ok(items)
}

/// 获取模型配置总数(与列表过滤条件保持一致)
pub async fn count(
    db: &DatabaseConnection,
    model: Option<&str>,
    model_type: Option<&str>,
    server_type: Option<&str>,
    scope: Option<&str>,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
    filter_user_ids: Option<&[String]>,
) -> Result<i64, AppError> {
    let mut select = model_config::Entity::find();
    if let Some(cond) = filter_condition(
        model, model_type, server_type, scope, user_id, dept_id, is_admin, filter_user_ids,
    ) {
        select = select.filter(cond);
    }
    let total = select.count(db).await?;
    Ok(total as i64)
}

/// 滚动加载模型配置列表(带可见性过滤; 实际查询 limit+1 条用于 has_more 探测)
pub async fn get_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
    user_id: Option<&str>,
    dept_id: Option<&str>,
    is_admin: bool,
) -> Result<Vec<model_config::Model>, AppError> {
    let mut select = model_config::Entity::find();
    if let Some(vis) = visibility_condition(user_id, dept_id, is_admin) {
        select = select.filter(vis);
    }
    // 排序字段(默认 created_at; 与 Python getattr 口径对齐, 未知字段报错)
    let column = match params.sort_by.as_str() {
        "created_at" => model_config::Column::CreatedAt,
        "updated_at" => model_config::Column::UpdatedAt,
        "id" => model_config::Column::Id,
        "model" => model_config::Column::Model,
        other => {
            return Err(AppError::internal(format!("未知排序字段: {other}")));
        }
    };
    // 游标条件: UP 取比游标更新(更大)的数据, DOWN 取更早(更小)的
    if let Some(last_id) = &params.last_id {
        let last = model_config::Entity::find_by_id(last_id.to_owned())
            .one(db)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {last_id} 的模板")))?;
        let cur = match params.sort_by.as_str() {
            "updated_at" => last.updated_at.to_string(),
            "id" => last.id.clone(),
            "model" => last.model.clone(),
            _ => last
                .created_at
                .map(|t| t.to_string())
                .unwrap_or_default(),
        };
        select = match params.direction {
            ScrollDirection::Up => select.filter(column.gt(cur)),
            ScrollDirection::Down => select.filter(column.lt(cur)),
        };
    }
    select = match params.direction {
        ScrollDirection::Up => select.order_by_asc(column),
        ScrollDirection::Down => select.order_by_desc(column),
    };
    let items = select.limit((params.limit + 1).max(0) as u64).all(db).await?;
    Ok(items)
}

/// 按用户名模糊搜索用户ID列表(管理员按所有者用户名过滤场景, 对齐 UserDao.search_ids_by_username)
pub async fn search_user_ids_by_username(
    db: &DatabaseConnection,
    username: &str,
) -> Result<Vec<String>, AppError> {
    let users = module_authorization::do_::entity::user::Entity::find()
        .filter(module_authorization::do_::entity::user::Column::Username.contains(username))
        .all(db)
        .await?;
    Ok(users.into_iter().map(|u| u.id).collect())
}

/// 按ID取单个用户(启动 seed 公共模型归属用; 异常按 None 处理与 Python 宽松口径一致)
pub async fn get_user_by_id(
    db: &DatabaseConnection,
    user_id: &str,
) -> Option<module_authorization::do_::entity::user::Model> {
    module_authorization::do_::entity::user::Entity::find_by_id(user_id.to_owned())
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 按用户名精确取用户(seed 归属管理员解析用)
pub async fn get_user_by_username(
    db: &DatabaseConnection,
    username: &str,
) -> Option<module_authorization::do_::entity::user::Model> {
    module_authorization::do_::entity::user::Entity::find()
        .filter(module_authorization::do_::entity::user::Column::Username.eq(username))
        .one(db)
        .await
        .ok()
        .flatten()
}

/// 按主键更新单条记录的 extra 字段(语音 server_type 归一化迁移用)
pub async fn update_extra_raw(
    db: &DatabaseConnection,
    id: &str,
    server_type: &str,
    extra: &serde_json::Value,
) -> Result<(), AppError> {
    model_config::Entity::update_many()
        .col_expr(model_config::Column::ServerType, Expr::value(server_type.to_string()))
        .col_expr(model_config::Column::Extra, Expr::value(extra.clone()))
        .filter(model_config::Column::Id.eq(id))
        .exec(db)
        .await?;
    Ok(())
}

/// 查询语音类存量记录(model_type asr/tts/vad/denoise 且 server_type 为历史值)
pub async fn list_legacy_voice_rows(
    db: &DatabaseConnection,
) -> Result<Vec<model_config::Model>, AppError> {
    let rows = model_config::Entity::find()
        .filter(
            Condition::all().add(model_config::Column::ModelType.is_in([
                "asr".to_string(),
                "tts".to_string(),
                "vad".to_string(),
                "denoise".to_string(),
            ])),
        )
        .filter(
            Condition::all().add(model_config::Column::ServerType.is_in([
                "dashscope".to_string(),
                "sherpa".to_string(),
                "qwen".to_string(),
            ])),
        )
        .all(db)
        .await?;
    Ok(rows)
}
