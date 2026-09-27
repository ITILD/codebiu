//! 同义词控制器(对齐 Python module_nlp/controller/synonym.py)
//!
//! 路由前缀 /nlp/synonyms: 同义词组(创建/更新/删除/批量删除/分页/滚动/详情)与
//! 同义词(批量创建/批量增量更新/删除/批量删除/单词搜索/批量搜索/分组聚合)。
//! 控制器只做请求解析/权限校验/响应包装, 业务规则与数据读写分别在 services/dao 层。

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::routing::{delete, get, post, put};
use axum::{Json, Router};
use serde::Deserialize;

use crate::do_::entity::synonym;
use crate::do_::entity::synonym_group;
use module_authorization::do_::entity::user;
use module_authorization::deps::{authorize, AuthUser};

use common::utils::extract::{AppJson, AppQuery};
use common::runtime::AppState;
use common::utils::error::{AppError, ValidationErrorItem};
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::do_::synonym::{
    BatchIdsRequest, SynonymBatchCreate, SynonymBatchSearch, SynonymBatchSearchResult,
    SynonymBatchUpdate, SynonymGroupCreate, SynonymGroupUpdate,
};
use crate::services;

/// nlp:synonym_group 资源权限校验
async fn require_group_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "nlp", "synonym_group", act).await
}

/// nlp:synonym 资源权限校验
async fn require_synonym_perm(user: &user::Model, act: &str) -> Result<(), AppError> {
    authorize(&user.id, "nlp", "synonym", act).await
}

/// 必填查询参数校验(缺失构造 422, type=missing 与 FastAPI 一致)
fn required_query(value: &Option<String>, field: &str) -> Result<String, AppError> {
    value.clone().ok_or_else(|| {
        AppError::Validation(vec![ValidationErrorItem {
            loc: vec!["query".to_string(), field.to_string()],
            msg: "Field required".to_string(),
            error_type: "missing".to_string(),
        }])
    })
}

/// 通用项目ID查询参数
#[derive(Debug, Default, Deserialize)]
pub struct PidQuery {
    /// 项目ID(必填)
    #[serde(default)]
    pub pid: Option<String>,
}

// ############################# 同义词组 #############################

/// POST /groups —— 创建同义词组(201; 返回组ID)
pub async fn create_synonym_group(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(data): AppJson<SynonymGroupCreate>,
) -> Result<(StatusCode, Json<String>), AppError> {
    require_group_perm(&actor, "create").await?;
    let id = services::synonym::group_add(&state.db, data).await?;
    Ok((StatusCode::CREATED, Json(id)))
}

/// GET /groups/scroll?pid —— 同义词组无限滚动(按项目过滤)
///
/// 说明: Python DAO 缺少 get_scroll_by_pid 方法(运行时会 AttributeError),
/// 按方法名与 count_by_pid/list_paged_by_pid 的语义等价实现为 pid 过滤滚动查询。
pub async fn synonym_group_infinite_scroll(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppQuery(params): AppQuery<InfiniteScrollParams>,
) -> Result<Json<InfiniteScrollResponse<synonym_group::Model>>, AppError> {
    require_group_perm(&actor, "read").await?;
    let pid = required_query(&q.pid, "pid")?;
    let page = services::synonym::group_scroll(&state.db, &params, &pid).await?;
    Ok(Json(page))
}

/// GET /groups/list?pid —— 分页查询指定项目下的同义词组(响应附带总数)
pub async fn list_synonym_groups(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppQuery(pagination): AppQuery<PaginationParams>,
) -> Result<Json<PaginationResponse<synonym_group::Model>>, AppError> {
    require_group_perm(&actor, "read").await?;
    let pid = required_query(&q.pid, "pid")?;
    pagination.validate()?;
    let page = services::synonym::group_list_paged(&state.db, &pagination, &pid).await?;
    Ok(Json(page))
}

/// GET /groups/{group_id}?pid —— 获取单个同义词组详情(不存在 404 "同义词组未找到")
pub async fn get_synonym_group(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(group_id): Path<String>,
    AppQuery(q): AppQuery<PidQuery>,
) -> Result<Json<synonym_group::Model>, AppError> {
    require_group_perm(&actor, "read").await?;
    let pid = required_query(&q.pid, "pid")?;
    let group = services::synonym::group_get(&state.db, &group_id, &pid).await?;
    Ok(Json(group))
}

/// GET /groups/{group_id}/synonyms —— 获取同义词组的所有同义词(仅返回词语列表)
pub async fn get_synonyms_by_group(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(group_id): Path<String>,
) -> Result<Json<Vec<String>>, AppError> {
    require_synonym_perm(&actor, "read").await?;
    let words = services::synonym::group_words(&state.db, &group_id).await?;
    Ok(Json(words))
}

/// DELETE /groups/{group_id}?pid —— 删除同义词组并级联删除组内全部同义词(204)
pub async fn delete_synonym_group(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(group_id): Path<String>,
    AppQuery(q): AppQuery<PidQuery>,
) -> Result<StatusCode, AppError> {
    require_group_perm(&actor, "delete").await?;
    let pid = required_query(&q.pid, "pid")?;
    services::synonym::group_delete(&state.db, &group_id, &pid).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /groups/batch?pid —— 批量删除指定项目下的同义词组(级联删除组内同义词)
pub async fn batch_delete_synonym_groups(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppJson(batch_delete): AppJson<BatchIdsRequest>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_group_perm(&actor, "delete").await?;
    let pid = required_query(&q.pid, "pid")?;
    batch_delete.validate()?;
    let deleted_count =
        services::synonym::group_batch_delete(&state.db, batch_delete.ids, &pid).await?;
    Ok(Json(serde_json::json!({ "deleted_count": deleted_count })))
}

/// PUT /groups?group_id —— 更新同义词组(204; 仅显式传入字段生效; 不存在 404)
///
/// group_id 为查询参数(对齐 Python 裸 str 参数 → query 注入)。
pub async fn update_synonym_group(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(query): AppQuery<GroupIdQuery>,
    AppJson(data): AppJson<SynonymGroupUpdate>,
) -> Result<StatusCode, AppError> {
    require_group_perm(&actor, "update").await?;
    let group_id = required_query(&query.group_id, "group_id")?;
    services::synonym::group_update(&state.db, &group_id, data).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// PUT /groups 查询参数
#[derive(Debug, Default, Deserialize)]
pub struct GroupIdQuery {
    /// 同义词组ID(必填)
    #[serde(default)]
    pub group_id: Option<String>,
}

// ############################# 同义词 #############################

/// POST /groups/batch —— 在指定项目/同义词组下批量插入词语(201; 返回ID列表)
pub async fn batch_create_synonyms(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppJson(batch_create): AppJson<SynonymBatchCreate>,
) -> Result<(StatusCode, Json<Vec<String>>), AppError> {
    require_synonym_perm(&actor, "create").await?;
    let ids = services::synonym::batch_create(&state.db, batch_create).await?;
    Ok((StatusCode::CREATED, Json(ids)))
}

/// PUT /synonyms/batch/{group_id} —— 以请求词语集合为目标, 增量同步组内词语(200)
pub async fn batch_update_synonyms(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(group_id): Path<String>,
    AppJson(batch_update): AppJson<SynonymBatchUpdate>,
) -> Result<(StatusCode, Json<serde_json::Value>), AppError> {
    require_synonym_perm(&actor, "update").await?;
    services::synonym::batch_update_incremental(&state.db, &group_id, &batch_update).await?;
    // 对齐 Python: 返回 None, 状态码 200
    Ok((StatusCode::OK, Json(serde_json::Value::Null)))
}

/// DELETE /synonyms/{synonym_id}?pid —— 按ID删除指定项目下的单个同义词(204)
pub async fn delete_synonym(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    Path(synonym_id): Path<String>,
    AppQuery(q): AppQuery<PidQuery>,
) -> Result<StatusCode, AppError> {
    require_synonym_perm(&actor, "delete").await?;
    let pid = required_query(&q.pid, "pid")?;
    services::synonym::delete(&state.db, &synonym_id, &pid).await?;
    Ok(StatusCode::NO_CONTENT)
}

/// DELETE /synonyms/batch?pid —— 按ID列表批量删除指定项目下的同义词
pub async fn batch_delete_synonyms(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppJson(batch_delete): AppJson<BatchIdsRequest>,
) -> Result<Json<serde_json::Value>, AppError> {
    require_synonym_perm(&actor, "delete").await?;
    let pid = required_query(&q.pid, "pid")?;
    batch_delete.validate()?;
    let deleted_count = services::synonym::batch_delete(&state.db, batch_delete.ids, &pid).await?;
    Ok(Json(serde_json::json!({ "deleted_count": deleted_count })))
}

/// GET /synonyms/search?word&pid&language —— 单个词语搜索其所在组的所有同义词
pub async fn search_synonyms(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<SearchQuery>,
) -> Result<Json<Vec<synonym::Model>>, AppError> {
    require_synonym_perm(&actor, "read").await?;
    let word = required_query(&q.word, "word")?;
    let pid = required_query(&q.pid, "pid")?;
    let items = services::synonym::search(&state.db, &word, &pid, q.language.as_ref()).await?;
    Ok(Json(items))
}

/// 搜索查询参数
#[derive(Debug, Default, Deserialize)]
pub struct SearchQuery {
    /// 要搜索的词语(必填)
    #[serde(default)]
    pub word: Option<String>,
    /// 项目ID(必填)
    #[serde(default)]
    pub pid: Option<String>,
    /// 语言代码(可选)
    #[serde(default)]
    pub language: Option<String>,
}

/// POST /synonyms/search/batch?pid —— 批量词语搜索(返回组内全部同义词记录)
pub async fn batch_search_synonyms(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppJson(request): AppJson<SynonymBatchSearch>,
) -> Result<Json<Vec<synonym::Model>>, AppError> {
    require_synonym_perm(&actor, "read").await?;
    let pid = required_query(&q.pid, "pid")?;
    let items =
        services::synonym::batch_search(&state.db, &request.words, &pid, request.language.as_ref())
            .await?;
    Ok(Json(items))
}

/// POST /synonyms/search/batch-group?pid —— 同义词簇聚合(同组输入词合并 + 扩展同义词)
pub async fn get_synonym_group_classified_results(
    state: State<AppState>,
    AuthUser(actor): AuthUser,
    AppQuery(q): AppQuery<PidQuery>,
    AppJson(request): AppJson<SynonymBatchSearch>,
) -> Result<Json<Vec<SynonymBatchSearchResult>>, AppError> {
    require_synonym_perm(&actor, "read").await?;
    let pid = required_query(&q.pid, "pid")?;
    let results = services::synonym::classify_clusters(
        &state.db,
        &request.words,
        &pid,
        request.language.as_ref(),
    )
    .await?;
    Ok(Json(results))
}

/// 同义词子路由(nest 到 /nlp/synonyms 前缀)
pub fn router() -> Router<AppState> {
    Router::new()
        .route("/groups", post(create_synonym_group).put(update_synonym_group))
        .route("/groups/batch", post(batch_create_synonyms).delete(batch_delete_synonym_groups))
        .route("/groups/scroll", get(synonym_group_infinite_scroll))
        .route("/groups/list", get(list_synonym_groups))
        .route("/groups/{group_id}/synonyms", get(get_synonyms_by_group))
        .route(
            "/groups/{group_id}",
            get(get_synonym_group).delete(delete_synonym_group),
        )
        .route("/synonyms/batch/{group_id}", put(batch_update_synonyms))
        .route("/synonyms/search", get(search_synonyms))
        .route("/synonyms/search/batch", post(batch_search_synonyms))
        .route(
            "/synonyms/search/batch-group",
            post(get_synonym_group_classified_results),
        )
        .route("/synonyms/batch", delete(batch_delete_synonyms))
        .route("/synonyms/{synonym_id}", delete(delete_synonym))
}
