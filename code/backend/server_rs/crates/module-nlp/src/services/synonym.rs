//! 同义词服务: 同义词组管理/批量同步/搜索与簇聚合

use std::collections::{BTreeSet, HashMap, HashSet};

use sea_orm::DatabaseConnection;

use crate::do_::entity::{synonym, synonym_group};

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::dao;
use crate::do_::synonym::{
    SynonymBatchCreate, SynonymBatchSearchResult, SynonymBatchUpdate, SynonymGroupCreate,
    SynonymGroupUpdate,
};

// ############################# 同义词组 #############################

/// 创建同义词组
///
/// :return: 新建组ID
pub async fn group_add(
    db: &DatabaseConnection,
    data: SynonymGroupCreate,
) -> Result<String, AppError> {
    dao::synonym::group_add(db, data).await
}

/// 同义词组无限滚动(按项目过滤; 游标过滤与排序在 dao 层, 此处组装响应)
pub async fn group_scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
    pid: &str,
) -> Result<InfiniteScrollResponse<synonym_group::Model>, AppError> {
    let items = dao::synonym::group_scroll(db, params, pid).await?;
    Ok(InfiniteScrollResponse::create(
        items,
        params.limit,
        params.direction,
        |m| m.id.clone(),
    ))
}

/// 分页查询指定项目下的同义词组(响应附带总数)
pub async fn group_list_paged(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
    pid: &str,
) -> Result<PaginationResponse<synonym_group::Model>, AppError> {
    let total = dao::synonym::group_count(db, pid).await?;
    let items = dao::synonym::group_list_paged(db, pagination, pid).await?;
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 获取同义词组详情(不存在或归属不符 404 "同义词组未找到")
pub async fn group_get(
    db: &DatabaseConnection,
    group_id: &str,
    pid: &str,
) -> Result<synonym_group::Model, AppError> {
    dao::synonym::group_get_by_id_and_pid(db, group_id, pid)
        .await?
        .ok_or_else(|| AppError::not_found("同义词组未找到"))
}

/// 删除同义词组并级联删除组内全部同义词(不存在 404; 不属于该项目 404)
pub async fn group_delete(
    db: &DatabaseConnection,
    group_id: &str,
    pid: &str,
) -> Result<(), AppError> {
    let group = dao::synonym::group_get_by_id(db, group_id)
        .await?
        .ok_or_else(|| {
            AppError::not_found(format!("未找到ID为 {group_id} 的同义词组"))
        })?;
    if group.pid != pid {
        return Err(AppError::not_found(format!("同义词组不属于项目 {pid}")));
    }
    // 先删组内同义词, 再删组
    dao::synonym::delete_group_words(db, group_id).await?;
    dao::synonym::group_delete(db, group_id).await
}

/// 批量删除同义词组(级联删除组内同义词; 只删除属于该项目的组, 不存在的ID静默跳过)
///
/// :return: 实际删除的组数量
pub async fn group_batch_delete(
    db: &DatabaseConnection,
    ids: Vec<String>,
    pid: &str,
) -> Result<u64, AppError> {
    // 先筛选出属于该项目的组ID
    let group_ids = dao::synonym::group_ids_in_pid(db, ids, pid).await?;
    if group_ids.is_empty() {
        return Ok(0);
    }
    // 删除所有相关同义词, 再删组
    dao::synonym::delete_groups_words(db, group_ids.clone()).await?;
    dao::synonym::group_delete_many(db, group_ids).await
}

/// 更新同义词组(仅显式传入字段生效; 不存在 404)
pub async fn group_update(
    db: &DatabaseConnection,
    group_id: &str,
    data: SynonymGroupUpdate,
) -> Result<(), AppError> {
    dao::synonym::group_update(db, group_id, data).await
}

// ############################# 同义词 #############################

/// 查询同义词组下全部词语
pub async fn group_words(
    db: &DatabaseConnection,
    group_id: &str,
) -> Result<Vec<String>, AppError> {
    dao::synonym::words_of_group(db, group_id).await
}

/// 在指定项目/同义词组下批量插入词语
///
/// :return: 新记录ID列表
pub async fn batch_create(
    db: &DatabaseConnection,
    batch_create: SynonymBatchCreate,
) -> Result<Vec<String>, AppError> {
    let mut ids = Vec::with_capacity(batch_create.words.len());
    for word in &batch_create.words {
        let id = dao::synonym::synonym_add(
            db,
            &batch_create.pid,
            &batch_create.group_id,
            word,
            batch_create.language.clone(),
        )
        .await?;
        ids.push(id);
    }
    Ok(ids)
}

/// 以请求词语集合为目标, 增量同步组内词语(差集新增/删除)
///
/// :return: 变更数量(新增+删除)
pub async fn batch_update_incremental(
    db: &DatabaseConnection,
    group_id: &str,
    batch_update: &SynonymBatchUpdate,
) -> Result<i64, AppError> {
    // 现有词语集合(限定组与项目)
    let existing: HashSet<String> =
        dao::synonym::words_of_group_in_pid(db, group_id, &batch_update.pid)
            .await?
            .into_iter()
            .collect();
    let target: HashSet<String> = batch_update.words.iter().cloned().collect();
    let to_delete: Vec<String> = existing.difference(&target).cloned().collect();
    let to_add: Vec<String> = target.difference(&existing).cloned().collect();
    // 变更数量需在 to_delete 所有权转移前统计
    let changed = (to_add.len() + to_delete.len()) as i64;
    // 删除差集
    if !to_delete.is_empty() {
        dao::synonym::delete_words(db, group_id, &batch_update.pid, to_delete).await?;
    }
    // 新增差集
    for word in &to_add {
        dao::synonym::synonym_add(
            db,
            &batch_update.pid,
            group_id,
            word,
            batch_update.language.clone(),
        )
        .await?;
    }
    Ok(changed)
}

/// 按ID删除指定项目下的单个同义词(不存在 404)
pub async fn delete(
    db: &DatabaseConnection,
    synonym_id: &str,
    pid: &str,
) -> Result<(), AppError> {
    let deleted = dao::synonym::delete_by_id_and_pid(db, synonym_id, pid).await?;
    if deleted == 0 {
        return Err(AppError::not_found(format!(
            "未找到ID为 {synonym_id} 且项目ID为 {pid} 的同义词"
        )));
    }
    Ok(())
}

/// 按ID列表批量删除指定项目下的同义词(不存在的ID静默跳过)
///
/// :return: 实际删除数量
pub async fn batch_delete(
    db: &DatabaseConnection,
    ids: Vec<String>,
    pid: &str,
) -> Result<u64, AppError> {
    dao::synonym::delete_by_ids_and_pid(db, ids, pid).await
}

/// 单个词语搜索其所在组的所有同义词
///
/// 与 Python 联表查询等价的两步实现: 先取匹配词所在组的 group_id 集合,
/// 再取组内全部同义词(join 同表 distinct 与之等价)。
pub async fn search(
    db: &DatabaseConnection,
    word: &str,
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<synonym::Model>, AppError> {
    let words = vec![word.to_string()];
    let group_ids = dao::synonym::matched_group_ids(db, &words, pid, language).await?;
    if group_ids.is_empty() {
        return Ok(Vec::new());
    }
    dao::synonym::find_by_group_ids(db, group_ids).await
}

/// 批量词语搜索(返回组内全部同义词记录)
pub async fn batch_search(
    db: &DatabaseConnection,
    words: &[String],
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<synonym::Model>, AppError> {
    let group_ids = dao::synonym::matched_group_ids(db, words, pid, language).await?;
    if group_ids.is_empty() {
        return Ok(Vec::new());
    }
    dao::synonym::find_by_group_ids(db, group_ids).await
}

/// 同义词簇聚合(对齐 Python get_synonym_group_classified_results 业务逻辑)
///
/// 步骤: 匹配输入词记录 → 按组收集输入词 → 拉取组内全部词语 → 扩展同义词 = 组内词语 - 输入词。
/// 说明: Python DAO 缺少 get_words_by_group_ids 方法(运行时会 AttributeError),
/// 按调用处语义(group_words.get(group_id, []))等价实现为按组聚合词语列表。
pub async fn classify_clusters(
    db: &DatabaseConnection,
    words: &[String],
    pid: &str,
    language: Option<&String>,
) -> Result<Vec<SynonymBatchSearchResult>, AppError> {
    // 1) 匹配输入词的同义词记录
    let matched = dao::synonym::find_matched(db, words, pid, language).await?;

    // 2) 按组收集输入词(BTreeSet 保证输出顺序稳定)
    let mut input_by_group: HashMap<String, BTreeSet<String>> = HashMap::new();
    for s in &matched {
        if words.contains(&s.word) {
            input_by_group
                .entry(s.group_id.clone())
                .or_default()
                .insert(s.word.clone());
        }
    }

    // 3) 批量获取相关同义词组的完整词语列表
    let group_ids: Vec<String> = input_by_group.keys().cloned().collect();
    let mut words_by_group: HashMap<String, Vec<String>> = HashMap::new();
    if !group_ids.is_empty() {
        for s in dao::synonym::find_by_group_ids_in_pid(db, group_ids, pid, language).await? {
            words_by_group
                .entry(s.group_id.clone())
                .or_default()
                .push(s.word);
        }
    }

    // 4) 扩展同义词 = 组内全部词语排除输入词
    Ok(input_by_group
        .into_iter()
        .map(|(group_id, inputs)| {
            let synonyms = words_by_group
                .get(&group_id)
                .map(|ws| {
                    ws.iter()
                        .filter(|w| !inputs.contains(*w))
                        .cloned()
                        .collect()
                })
                .unwrap_or_default();
            SynonymBatchSearchResult {
                words: inputs.into_iter().collect(),
                synonyms,
            }
        })
        .collect())
}
