//! 同义词数据访问(对齐 Python module_nlp/dao/synonym.py)
//!
//! 同义词组与同义词两组自由函数; 归属校验(404)/差集计算/簇聚合在 services 层。

use sea_orm::sea_query::Expr;
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, PaginatorTrait, QueryFilter,
    QueryOrder, QuerySelect, Select, Set,
};
use uuid::Uuid;

use crate::do_::entity::{synonym, synonym_group};

use common::utils::error::AppError;
use common::utils::pagination::{InfiniteScrollParams, PaginationParams, ScrollDirection};

use crate::do_::now_utc;
use crate::do_::synonym::{SynonymGroupCreate, SynonymGroupUpdate};

// ############################# 同义词组 #############################

/// 新增同义词组记录(未传 is_active 取 Python 模型默认值 true)
///
/// :return: 新创建组ID
pub async fn group_add(
    db: &DatabaseConnection,
    data: SynonymGroupCreate,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = synonym_group::ActiveModel {
        id: Set(id.clone()),
        pid: Set(data.pid),
        name: Set(data.name),
        description: Set(data.description),
        is_active: Set(Some(data.is_active.unwrap_or(true))),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 按 ID 查询同义词组(不限项目, 供服务层做归属判定)
pub async fn group_get_by_id(
    db: &DatabaseConnection,
    group_id: &str,
) -> Result<Option<synonym_group::Model>, AppError> {
    Ok(synonym_group::Entity::find_by_id(group_id.to_owned())
        .one(db)
        .await?)
}

/// 按 ID+项目 查询同义词组(详情查询, 归属不符视为不存在)
pub async fn group_get_by_id_and_pid(
    db: &DatabaseConnection,
    group_id: &str,
    pid: &str,
) -> Result<Option<synonym_group::Model>, AppError> {
    Ok(synonym_group::Entity::find()
        .filter(synonym_group::Column::Id.eq(group_id))
        .filter(synonym_group::Column::Pid.eq(pid))
        .one(db)
        .await?)
}

/// 项目过滤查询构建(列表/计数共用)
fn group_select_by_pid(pid: &str) -> Select<synonym_group::Entity> {
    synonym_group::Entity::find().filter(synonym_group::Column::Pid.eq(pid))
}

/// 同义词组无限滚动(按项目过滤; 游标记录不存在 404; limit+1 探测 has_more)
pub async fn group_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
    pid: &str,
) -> Result<Vec<synonym_group::Model>, AppError> {
    let col = group_sort_column(&params.sort_by)?;
    let mut select = group_select_by_pid(pid);
    if let Some(last_id) = &params.last_id {
        let last = synonym_group::Entity::find_by_id(last_id)
            .one(db)
            .await?
            .ok_or_else(|| {
                AppError::not_found(format!("未找到ID为 {last_id} 的同义词组"))
            })?;
        let value = group_sort_value(col, &last);
        select = match params.direction {
            ScrollDirection::Up => select.filter(col.gt(value)),
            ScrollDirection::Down => select.filter(col.lt(value)),
        };
    }
    select = match params.direction {
        ScrollDirection::Up => select.order_by_asc(col),
        ScrollDirection::Down => select.order_by_desc(col),
    };
    let items = select
        .limit(params.limit.max(0) as u64 + 1)
        .all(db)
        .await?;
    Ok(items)
}

/// 统计指定项目下的同义词组总数
pub async fn group_count(db: &DatabaseConnection, pid: &str) -> Result<i64, AppError> {
    let total = group_select_by_pid(pid).count(db).await?;
    Ok(total as i64)
}

/// 分页查询指定项目下的同义词组
pub async fn group_list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    pid: &str,
) -> Result<Vec<synonym_group::Model>, AppError> {
    Ok(group_select_by_pid(pid)
        .offset(pagination.offset())
        .limit(pagination.limit())
        .all(db)
        .await?)
}

/// 删除同义词组下的全部同义词
pub async fn delete_group_words(db: &DatabaseConnection, group_id: &str) -> Result<(), AppError> {
    synonym::Entity::delete_many()
        .filter(synonym::Column::GroupId.eq(group_id))
        .exec(db)
        .await?;
    Ok(())
}

/// 删除同义词组记录
pub async fn group_delete(db: &DatabaseConnection, group_id: &str) -> Result<(), AppError> {
    synonym_group::Entity::delete_many()
        .filter(synonym_group::Column::Id.eq(group_id))
        .exec(db)
        .await?;
    Ok(())
}

/// 筛选 ID 列表中属于指定项目的组ID
pub async fn group_ids_in_pid(
    db: &DatabaseConnection,
    ids: Vec<String>,
    pid: &str,
) -> Result<Vec<String>, AppError> {
    Ok(synonym_group::Entity::find()
        .filter(synonym_group::Column::Id.is_in(ids))
        .filter(synonym_group::Column::Pid.eq(pid))
        .select_only()
        .column(synonym_group::Column::Id)
        .into_tuple::<String>()
        .all(db)
        .await?)
}

/// 删除多个同义词组下的全部同义词
pub async fn delete_groups_words(
    db: &DatabaseConnection,
    group_ids: Vec<String>,
) -> Result<(), AppError> {
    synonym::Entity::delete_many()
        .filter(synonym::Column::GroupId.is_in(group_ids))
        .exec(db)
        .await?;
    Ok(())
}

/// 批量删除同义词组记录
///
/// :return: 实际删除数量
pub async fn group_delete_many(
    db: &DatabaseConnection,
    ids: Vec<String>,
) -> Result<u64, AppError> {
    let result = synonym_group::Entity::delete_many()
        .filter(synonym_group::Column::Id.is_in(ids))
        .exec(db)
        .await?;
    Ok(result.rows_affected)
}

/// 直接更新同义词组记录(不先查询, 仅显式传入字段生效;
/// updated_at 显式刷新对应 Python onupdate 语义)
///
/// :raises: AppError::not_found 组不存在
pub async fn group_update(
    db: &DatabaseConnection,
    group_id: &str,
    data: SynonymGroupUpdate,
) -> Result<(), AppError> {
    let mut update = synonym_group::Entity::update_many()
        .col_expr(synonym_group::Column::UpdatedAt, Expr::value(now_utc()));
    if let Some(v) = data.pid {
        update = update.col_expr(synonym_group::Column::Pid, Expr::value(v));
    }
    if let Some(v) = data.name {
        update = update.col_expr(synonym_group::Column::Name, Expr::value(v));
    }
    if let Some(v) = data.description {
        update = update.col_expr(synonym_group::Column::Description, Expr::value(v));
    }
    if let Some(v) = data.is_active {
        update = update.col_expr(synonym_group::Column::IsActive, Expr::value(v));
    }
    let result = update
        .filter(synonym_group::Column::Id.eq(group_id))
        .exec(db)
        .await?;
    if result.rows_affected == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {group_id} 的同义词组"
        )));
    }
    Ok(())
}

// ############################# 同义词 #############################

/// 插入单个同义词记录
///
/// :return: 新记录ID
pub async fn synonym_add(
    db: &DatabaseConnection,
    pid: &str,
    group_id: &str,
    word: &str,
    language: Option<String>,
) -> Result<String, AppError> {
    let id = Uuid::new_v4().simple().to_string();
    let am = synonym::ActiveModel {
        id: Set(id.clone()),
        pid: Set(pid.to_string()),
        group_id: Set(group_id.to_string()),
        word: Set(word.to_string()),
        language: Set(language),
        created_at: Set(Some(now_utc())),
        updated_at: Set(now_utc()),
    };
    am.insert(db).await?;
    Ok(id)
}

/// 查询同义词组下全部词语
pub async fn words_of_group(
    db: &DatabaseConnection,
    group_id: &str,
) -> Result<Vec<String>, AppError> {
    Ok(synonym::Entity::find()
        .filter(synonym::Column::GroupId.eq(group_id))
        .select_only()
        .column(synonym::Column::Word)
        .into_tuple::<String>()
        .all(db)
        .await?)
}

/// 查询组内现有词语(限定组与项目, 供差集同步使用)
pub async fn words_of_group_in_pid(
    db: &DatabaseConnection,
    group_id: &str,
    pid: &str,
) -> Result<Vec<String>, AppError> {
    Ok(synonym::Entity::find()
        .filter(synonym::Column::GroupId.eq(group_id))
        .filter(synonym::Column::Pid.eq(pid))
        .select_only()
        .column(synonym::Column::Word)
        .into_tuple::<String>()
        .all(db)
        .await?)
}

/// 删除组内指定词语(限定组与项目)
pub async fn delete_words(
    db: &DatabaseConnection,
    group_id: &str,
    pid: &str,
    words: Vec<String>,
) -> Result<(), AppError> {
    synonym::Entity::delete_many()
        .filter(synonym::Column::GroupId.eq(group_id))
        .filter(synonym::Column::Pid.eq(pid))
        .filter(synonym::Column::Word.is_in(words))
        .exec(db)
        .await?;
    Ok(())
}

/// 按 ID+项目 删除单个同义词
///
/// :return: 实际删除行数
pub async fn delete_by_id_and_pid(
    db: &DatabaseConnection,
    synonym_id: &str,
    pid: &str,
) -> Result<u64, AppError> {
    let result = synonym::Entity::delete_many()
        .filter(synonym::Column::Id.eq(synonym_id))
        .filter(synonym::Column::Pid.eq(pid))
        .exec(db)
        .await?;
    Ok(result.rows_affected)
}

/// 按 ID 列表+项目 批量删除同义词
///
/// :return: 实际删除数量
pub async fn delete_by_ids_and_pid(
    db: &DatabaseConnection,
    ids: Vec<String>,
    pid: &str,
) -> Result<u64, AppError> {
    let result = synonym::Entity::delete_many()
        .filter(synonym::Column::Id.is_in(ids))
        .filter(synonym::Column::Pid.eq(pid))
        .exec(db)
        .await?;
    Ok(result.rows_affected)
}

/// 查询匹配词语所在的 group_id 集合(去重, 对齐 search_by_word/batch_search_by_words 子查询)
pub async fn matched_group_ids(
    db: &DatabaseConnection,
    words: &[String],
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<String>, AppError> {
    let mut select = synonym::Entity::find()
        .filter(synonym::Column::Word.is_in(words.to_vec()))
        .filter(synonym::Column::Pid.eq(pid))
        .select_only()
        .column(synonym::Column::GroupId)
        .distinct();
    if let Some(lang) = language {
        select = select.filter(synonym::Column::Language.eq(lang));
    }
    Ok(select.into_tuple::<String>().all(db).await?)
}

/// 查询同义词组集合下的全部同义词记录
pub async fn find_by_group_ids(
    db: &DatabaseConnection,
    group_ids: Vec<String>,
) -> Result<Vec<synonym::Model>, AppError> {
    Ok(synonym::Entity::find()
        .filter(synonym::Column::GroupId.is_in(group_ids))
        .all(db)
        .await?)
}

/// 查询匹配输入词的同义词记录(限定项目, 可按语言过滤)
pub async fn find_matched(
    db: &DatabaseConnection,
    words: &[String],
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<synonym::Model>, AppError> {
    let mut matched = synonym::Entity::find()
        .filter(synonym::Column::Word.is_in(words.to_vec()))
        .filter(synonym::Column::Pid.eq(pid));
    if let Some(lang) = language {
        matched = matched.filter(synonym::Column::Language.eq(lang));
    }
    Ok(matched.all(db).await?)
}

/// 查询同义词组集合下、指定项目的全部同义词记录(可按语言过滤)
pub async fn find_by_group_ids_in_pid(
    db: &DatabaseConnection,
    group_ids: Vec<String>,
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<synonym::Model>, AppError> {
    let mut all = synonym::Entity::find()
        .filter(synonym::Column::GroupId.is_in(group_ids))
        .filter(synonym::Column::Pid.eq(pid));
    if let Some(lang) = language {
        all = all.filter(synonym::Column::Language.eq(lang));
    }
    Ok(all.all(db).await?)
}

/// 将排序字段名映射为列(未知字段报 500, 对齐 Python getattr 的 AttributeError 行为)
fn group_sort_column(sort_by: &str) -> Result<synonym_group::Column, AppError> {
    Ok(match sort_by {
        "pid" => synonym_group::Column::Pid,
        "name" => synonym_group::Column::Name,
        "description" => synonym_group::Column::Description,
        "is_active" => synonym_group::Column::IsActive,
        "id" => synonym_group::Column::Id,
        "created_at" => synonym_group::Column::CreatedAt,
        "updated_at" => synonym_group::Column::UpdatedAt,
        _ => {
            return Err(AppError::Internal(format!(
                "无效的排序字段: {sort_by}"
            )))
        }
    })
}

/// 取排序字段在指定记录上的值(用于游标比较)
fn group_sort_value(
    col: synonym_group::Column,
    m: &synonym_group::Model,
) -> sea_orm::sea_query::Value {
    match col {
        synonym_group::Column::Pid => m.pid.clone().into(),
        synonym_group::Column::Name => m.name.clone().into(),
        synonym_group::Column::Description => m.description.clone().into(),
        synonym_group::Column::IsActive => m.is_active.into(),
        synonym_group::Column::Id => m.id.clone().into(),
        synonym_group::Column::CreatedAt => m.created_at.into(),
        synonym_group::Column::UpdatedAt => m.updated_at.into(),
    }
}
