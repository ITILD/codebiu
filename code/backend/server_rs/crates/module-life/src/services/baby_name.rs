//! 宝宝取名服务: 参考体系推算编排 + 模型可用性校验 + 名字管理业务规则

use std::collections::BTreeMap;

use sea_orm::DatabaseConnection;

use common::utils::error::AppError;
use common::utils::pagination::{
    InfiniteScrollParams, InfiniteScrollResponse, PaginationParams, PaginationResponse,
};

use crate::dao;
use crate::do_::almanac::{ReferenceCalculateResult, SancaiBaseInfo, WuxingInfo, ZodiacInfo};
use crate::do_::baby_name::{BabyNameCreate, BabyNameOut, BabyNameUpdate};
use crate::do_::predict::{NameInfoBase, NameInfoPreference, ReferenceCalculateRequest};
use crate::utils::baby_name::folklore::Reference;
use crate::utils::baby_name::{almanac, constellation, folklore, religion, strokes, tarot, wuxing};

// ==================== 参考体系目录与推算 ====================

/// 获取起名参考体系目录(供前端多选卡片渲染)
pub fn get_reference_catalog() -> Vec<folklore::ReferenceCatalogItem> {
    folklore::get_reference_catalog()
}

/// 按选中参考体系做经典严格程序推算
///
/// 逐项调用 utils 算法模块, 按请求选择组装结果(未选体系为 null)。
pub fn calculate_reference(req: ReferenceCalculateRequest) -> Result<ReferenceCalculateResult, AppError> {
    let mut result = ReferenceCalculateResult::default();
    // Python: refs = set(request.references)
    let has = |r: Reference| req.references.contains(&r);

    if has(Reference::Wuxing) {
        let w = wuxing::analyze_wuxing(&req.birth_date, &req.birth_time)?;
        result.wuxing = Some(WuxingInfo {
            pillars: w.pillars,
            counts: w.counts,
            canggan: w.canggan,
            day_master: w.day_master,
            strength: w.strength,
            favorable: w.favorable,
            summary: w.summary,
        });
    }
    if has(Reference::Constellation) {
        result.constellation = Some(constellation::get_constellation(&req.birth_date)?);
    }
    if has(Reference::Zodiac) {
        // 生肖按年柱地支取(立春分界, 日期粒度)
        let zodiac = almanac::get_zodiac(&req.birth_date)?;
        let d = almanac::parse_birth_date(&req.birth_date)?;
        let (y_gan, y_zhi) = almanac::year_pillar(d, None);
        let year_ganzhi = format!("{}{}", almanac::gan_char(y_gan), almanac::zhi_char(y_zhi));
        let hint = almanac::zodiac_hint(&zodiac);
        result.zodiac = Some(ZodiacInfo {
            name: zodiac.clone(),
            year_ganzhi,
            favorable_chars: hint.to_string(),
            summary: format!("生肖{zodiac}。{hint}"),
        });
    }
    if has(Reference::Tarot) {
        result.tarot = Some(tarot::get_tarot(&req.birth_date)?);
    }
    if has(Reference::Sancai) {
        // 姓氏三才五格基准(仅天格; 动态键按字典序输出, 与 Python 插入序不同)
        let mut surname_strokes: BTreeMap<String, i32> = BTreeMap::new();
        let mut estimated: Vec<String> = Vec::new();
        for ch in req.surname.chars() {
            let (n, exact) = strokes::stroke_of(ch);
            surname_strokes.insert(ch.to_string(), n);
            if !exact {
                estimated.push(ch.to_string());
            }
        }
        let tian = surname_strokes.values().sum::<i32>()
            + if req.surname.chars().count() == 1 { 1 } else { 0 };
        result.sancai = Some(SancaiBaseInfo {
            surname_strokes,
            estimated_chars: estimated,
            tian_ge: tian,
            note: "天格由姓氏决定; 完整五格需待名字生成后逐个评定".to_string(),
        });
    }
    if has(Reference::Buddhism) {
        result.buddhism = Some(religion::get_benming_buddha(&req.birth_date)?);
    }
    if has(Reference::Taoism) {
        result.taoism = Some(religion::get_taishi(&req.birth_date)?);
    }
    if has(Reference::Christian) {
        result.christian = Some(religion::get_christian_theme(&req.birth_date)?);
    }
    Ok(result)
}

/// 严格推算五行喜用与星座偏好(经典算法, 非LLM估算)
pub fn predict_preference(req: NameInfoBase) -> Result<NameInfoPreference, AppError> {
    let w = wuxing::analyze_wuxing(&req.birth_date, &req.birth_time)?;
    let c = constellation::get_constellation(&req.birth_date)?;
    Ok(NameInfoPreference {
        wuxing_preference: w.favorable,
        constellation_preference: vec![c.name],
    })
}

// ==================== 模型可用性前置校验 ====================

/// 模型可用性前置校验(复刻 Python generate_names_stream 的回退链)
///
/// 指定 model_id 且配置存在 → 放行; 指定模型缺失/未指定 → 回退默认公共 chat 模型
/// (public + is_default + is_active), 仍无则 400 "未找到可用的默认 chat 模型..."。
pub async fn ensure_model_available(
    db: &DatabaseConnection,
    model_id: &str,
) -> Result<(), AppError> {
    if !model_id.is_empty() && dao::baby_name::model_exists(db, model_id).await? {
        return Ok(());
    }
    // 回退默认公共 chat 模型(active_only)
    if !dao::baby_name::default_chat_model_exists(db).await? {
        return Err(AppError::business(
            "未找到可用的默认 chat 模型, 请先在模型配置中添加并设为默认",
        ));
    }
    Ok(())
}

// ==================== 名字管理 ====================

/// 名字长度校验(与 Python field_validator 一致: 1-10 个字符)
fn validate_name(name: &str) -> Result<(), AppError> {
    let len = name.chars().count();
    if len < 1 || len > 10 {
        return Err(AppError::validation(
            &["body", "name"],
            "名字长度必须在1-10个字符之间",
        ));
    }
    Ok(())
}

/// 添加宝宝名字(名字长度校验 1-10 个字符)
///
/// :return: 新建名字ID
pub async fn create(db: &DatabaseConnection, data: BabyNameCreate) -> Result<String, AppError> {
    validate_name(&data.name)?;
    dao::baby_name::add(db, data).await
}

/// 分页查询宝宝名字列表(无排序, 与 Python list_paged 一致)
pub async fn list(
    db: &DatabaseConnection,
    pagination: &PaginationParams,
) -> Result<PaginationResponse<BabyNameOut>, AppError> {
    let total = dao::baby_name::count(db).await?;
    let items = dao::baby_name::list_paged(db, pagination)
        .await?
        .into_iter()
        .map(BabyNameOut::from)
        .collect();
    Ok(PaginationResponse::create(items, total, pagination))
}

/// 无限滚动加载宝宝名字列表(last_id 游标 + 排序字段)
pub async fn scroll(
    db: &DatabaseConnection,
    params: &InfiniteScrollParams,
) -> Result<InfiniteScrollResponse<BabyNameOut>, AppError> {
    let items = dao::baby_name::scroll(db, params)
        .await?
        .into_iter()
        .map(BabyNameOut::from)
        .collect();
    Ok(InfiniteScrollResponse::create(
        items,
        params.limit,
        params.direction,
        |b| b.id.clone(),
    ))
}

/// 获取单个宝宝名字详情(不存在 404 "名字不存在")
pub async fn get(db: &DatabaseConnection, name_id: &str) -> Result<BabyNameOut, AppError> {
    dao::baby_name::get(db, name_id)
        .await?
        .map(BabyNameOut::from)
        .ok_or_else(|| AppError::not_found("名字不存在"))
}

/// 更新宝宝名字(仅显式传入的字段生效)
///
/// Update 名字仅保留 max_length=50 约束(与 Python BabyNameUpdate 一致, 无 1-10 校验器)。
/// :raises: AppError::not_found 名字不存在
pub async fn update(
    db: &DatabaseConnection,
    name_id: &str,
    data: BabyNameUpdate,
) -> Result<(), AppError> {
    if let Some(name) = &data.name {
        if name.chars().count() > 50 {
            return Err(AppError::validation(
                &["body", "name"],
                "String should have at most 50 characters",
            ));
        }
    }
    dao::baby_name::update(db, name_id, data).await
}

/// 删除宝宝名字(不存在 404)
pub async fn delete(db: &DatabaseConnection, name_id: &str) -> Result<(), AppError> {
    dao::baby_name::delete(db, name_id).await
}

/// 批量删除宝宝名字
///
/// :return: 实际删除条数
pub async fn batch_delete(db: &DatabaseConnection, ids: Vec<String>) -> Result<i64, AppError> {
    dao::baby_name::batch_delete(db, ids).await
}
