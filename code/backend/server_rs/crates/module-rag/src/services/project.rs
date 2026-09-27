//! 项目/成员/部门授权业务服务(对齐 Python module_rag/service/project.py、
//! project_member.py、project_dept.py)

use std::collections::HashMap;

use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};
use sea_orm::{EntityTrait, Set};

use crate::dao::project as dao;
use crate::do_::entity::project;
use crate::do_::project::{
    validate_kb_category, validate_role, ProjectCreate, ProjectDeptCreate, ProjectDeptResponse,
    ProjectDeptUpdate, ProjectDeptWithDept, ProjectMemberCreate, ProjectMemberResponse,
    ProjectMemberUpdate, ProjectMemberWithUser, ProjectMyPerms, ProjectResponse, ProjectUpdate,
    MyProjectResponse, role_level,
};
use crate::services::permission::{enforce_project_permission, get_user_dept_chain};

/// 知识库模块在虚拟目录树中的模块根(source_module 标记 + 显示名)
const RAG_MODULE_KEY: &str = "rag";
const RAG_MODULE_LABEL: &str = "知识库";

/// 当前 UTC 时间(实体时间戳填充)
fn now_utc() -> sea_orm::prelude::DateTimeWithTimeZone {
    chrono::Utc::now().into()
}

/// 32 位 hex uuid(对齐 Python uuid4().hex)
fn new_id() -> String {
    uuid::Uuid::new_v4().simple().to_string()
}

/// 确保项目根文件夹存在并回写 root_entry_id(幂等, 惰性补建)
///
/// 虚拟目录: /知识库(rag模块根)/<项目名>(项目文件夹)
pub async fn ensure_project_folder(
    state: &AppState,
    project_id: &str,
    owner_user_id: Option<&str>,
) -> Result<String, AppError> {
    let project_model = dao::project_get(&state.db, project_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("项目 {project_id} 不存在")))?;
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);
    if let Some(root_id) = &project_model.root_entry_id {
        // 已关联的条目可能被外部删除 → 失效时重新补建
        if let Some(entry) = file_service.get_file_entry(root_id).await? {
            if entry.is_active {
                return Ok(root_id.clone());
            }
        }
    }
    // 幂等确保模块根与项目文件夹(重名残留直接复用)
    let module_root = file_service
        .ensure_module_root(RAG_MODULE_KEY, RAG_MODULE_LABEL, owner_user_id)
        .await?;
    let folder = file_service
        .ensure_folder(&project_model.name, Some(&module_root.id), owner_user_id)
        .await?;
    if project_model.root_entry_id.as_deref() != Some(folder.id.as_str()) {
        dao::project_update(&state.db, project_id, None, None, None, None, Some(folder.id.clone()))
            .await?;
    }
    Ok(folder.id)
}

/// 实体 → 响应(附带权限位)
fn to_response(m: project::Model, perms: Option<ProjectMyPerms>) -> ProjectResponse {
    ProjectResponse {
        id: m.id,
        name: m.name,
        description: m.description,
        is_private: m.is_private,
        kb_category: m.kb_category,
        created_by: m.created_by,
        root_entry_id: m.root_entry_id,
        created_at: m.created_at,
        updated_at: m.updated_at,
        my_perms: perms,
    }
}

// ==================== 项目服务 ====================

/// 创建项目, 自动将创建者设为项目管理员并创建项目根文件夹; 返回项目ID
pub async fn project_add(state: &AppState, req: ProjectCreate, user_id: &str) -> Result<String, AppError> {
    // 校验知识库分类合法性
    validate_kb_category(&req.kb_category).map_err(AppError::business)?;
    let project_id = new_id();
    dao::project_add(
        &state.db,
        project::ActiveModel {
            id: Set(project_id.clone()),
            name: Set(req.name),
            description: Set(req.description),
            is_private: Set(req.is_private),
            kb_category: Set(req.kb_category),
            created_by: Set(user_id.to_string()),
            root_entry_id: Set(None),
            created_at: Set(Some(now_utc())),
            updated_at: Set(now_utc()),
        },
    )
    .await?;
    // 自动将创建者添加为项目管理员
    dao::member_add(
        &state.db,
        crate::do_::entity::project_member::ActiveModel {
            id: Set(new_id()),
            user_id: Set(user_id.to_string()),
            project_id: Set(project_id.clone()),
            role: Set("project_admin".to_string()),
            created_at: Set(Some(now_utc())),
            updated_at: Set(now_utc()),
        },
    )
    .await?;
    // 创建项目根文件夹(虚拟目录 /知识库/<项目名>/)
    ensure_project_folder(state, &project_id, Some(user_id)).await?;
    Ok(project_id)
}

/// 删除项目并级联清理: 向量/项目文件夹/文档/成员/部门授权/项目本身
pub async fn project_delete(state: &AppState, project_id: &str) -> Result<(), AppError> {
    let project_model = dao::project_get(&state.db, project_id).await?;
    let docs = crate::dao::document::document_list_all_by_project(&state.db, project_id).await?;
    let file_service = module_file::services::filesystem::FileService::new(state.clone(), true);

    // 1. 删向量库(向量库引擎暂未在 Rust 服务实现, 分块表随文档记录级联清理)
    crate::dao::document::chunk_delete_by_project(&state.db, project_id).await?;

    // 2. 删项目根文件夹(条目级文档的内容引用随子树删除统一释放)
    if let Some(root_id) = project_model.as_ref().and_then(|p| p.root_entry_id.clone()) {
        if let Err(e) = file_service.delete_folder(&root_id).await {
            tracing::warn!("删除项目文件夹失败 {root_id}: {e}");
        }
    }

    // 3. 清理非条目口径文档的物理内容(内容级旧数据兼容)
    for doc in &docs {
        if doc.entry_id.is_some() {
            continue;
        }
        if let Some(hash) = &doc.content_hash {
            if let Err(e) = file_service.release_content_public(Some(hash)).await {
                tracing::warn!("释放文档内容引用失败 {}: {e}", doc.id);
            }
        }
    }

    // 4/5/6. 删 db 文档/成员/部门授权记录
    let deleted_docs = crate::dao::document::document_delete_by_project(&state.db, project_id).await?;
    let deleted_members = dao::member_delete_by_project(&state.db, project_id).await?;
    let deleted_depts = dao::dept_delete_by_project(&state.db, project_id).await?;
    tracing::info!(
        "删除项目 {project_id}: 已清理 {deleted_docs} 个文档记录, {deleted_members} 个成员记录, {deleted_depts} 个部门授权记录"
    );

    // 8. 删项目本身
    dao::project_delete(&state.db, project_id).await?;
    Ok(())
}

/// 更新项目(分类校验 + is_private 变更需要 project_admin 档位 + 名称变更同步重命名文件夹)
pub async fn project_update(
    state: &AppState,
    project_id: &str,
    req: ProjectUpdate,
    user_id: &str,
) -> Result<(), AppError> {
    if let Some(category) = &req.kb_category {
        validate_kb_category(category).map_err(AppError::business)?;
    }
    // publish 校验: 仅在本次提交确实改变 is_private 时执行
    if let Some(new_private) = req.is_private {
        let existing = dao::project_get(&state.db, project_id)
            .await?
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {project_id} 的项目")))?;
        if new_private != existing.is_private {
            enforce_project_permission(state, user_id, project_id, "project", "publish").await?;
        }
    }
    let description = req.description.clone().map(Some);
    dao::project_update(
        &state.db,
        project_id,
        req.name.clone(),
        description,
        req.is_private,
        req.kb_category.clone(),
        None,
    )
    .await?;
    // 名称变更: 同步重命名项目根文件夹(失败仅告警, 不影响项目更新)
    if let Some(name) = &req.name {
        if let Some(p) = dao::project_get(&state.db, project_id).await? {
            if let Some(root_id) = p.root_entry_id {
                let file_service =
                    module_file::services::filesystem::FileService::new(state.clone(), true);
                if let Err(e) = file_service.rename(&root_id, name).await {
                    tracing::warn!("项目文件夹重命名失败(可能同名) project={project_id}: {e}");
                }
            }
        }
    }
    Ok(())
}

/// 批量计算当前用户对多个项目的权限位(全局管理员全 True; 其余按档位映射)
pub async fn compute_my_perms(
    state: &AppState,
    user_id: &str,
    project_ids: &[String],
) -> Result<HashMap<String, ProjectMyPerms>, AppError> {
    let mut result = HashMap::new();
    if project_ids.is_empty() {
        return Ok(result);
    }
    if module_authorization::casbin_mgr::auth().is_global_admin(user_id).await {
        for pid in project_ids {
            result.insert(pid.clone(), ProjectMyPerms::full());
        }
        return Ok(result);
    }
    // 批量取直连成员档位 + 部门授权档位(部门链一次查询复用)
    let mut level_by_project: HashMap<String, i32> =
        project_ids.iter().map(|p| (p.clone(), 0)).collect();
    for (pid, role) in
        dao::member_list_roles_by_projects(&state.db, user_id, project_ids).await?
    {
        let entry = level_by_project.entry(pid).or_insert(0);
        *entry = (*entry).max(role_level(&role));
    }
    let dept_chain = get_user_dept_chain(&state.db, user_id).await?;
    if !dept_chain.is_empty() {
        for (pid, role) in
            dao::dept_list_roles_by_projects(&state.db, &dept_chain, project_ids).await?
        {
            let entry = level_by_project.entry(pid).or_insert(0);
            *entry = (*entry).max(role_level(&role));
        }
    }
    for (pid, level) in level_by_project {
        result.insert(pid, ProjectMyPerms::from_level(level));
    }
    Ok(result)
}

/// 分页获取项目列表(可见性过滤 + 权限位; viewer_id=None 表示管理员审计全量)
pub async fn project_list_paged(
    state: &AppState,
    pagination: &PaginationParams,
    kb_category: Option<String>,
    name: Option<String>,
    is_private: Option<bool>,
    viewer_id: Option<String>,
) -> Result<PaginationResponse<ProjectResponse>, AppError> {
    pagination.validate()?;
    let dept_chain = match &viewer_id {
        Some(v) => get_user_dept_chain(&state.db, v).await?,
        None => Vec::new(),
    };
    let items = dao::project_list_paged(
        &state.db,
        pagination.page,
        pagination.size,
        name.as_deref(),
        kb_category.as_deref(),
        is_private,
        viewer_id.as_deref(),
        &dept_chain,
    )
    .await?;
    let total = dao::project_count(
        &state.db,
        name.as_deref(),
        kb_category.as_deref(),
        is_private,
        viewer_id.as_deref(),
        &dept_chain,
    )
    .await?;
    // 权限位: 普通用户按档位批量计算; 管理员(viewer_id=None)全 True
    let mut perms_map: HashMap<String, ProjectMyPerms> = match &viewer_id {
        Some(v) => {
            let ids: Vec<String> = items.iter().map(|p| p.id.clone()).collect();
            compute_my_perms(state, v, &ids).await?
        }
        None => items
            .iter()
            .map(|p| (p.id.clone(), ProjectMyPerms::full()))
            .collect(),
    };
    // 公开库任何登录用户可只读(v4 3.2): 非成员档位 0 也标记 read
    let mut responses = Vec::with_capacity(items.len());
    for p in items {
        let perms = perms_map.remove(&p.id);
        let mut perms = match (viewer_id.is_some(), perms) {
            (true, Some(mut perm)) => {
                if !p.is_private {
                    perm.read = true;
                }
                Some(perm)
            }
            (true, None) => {
                let mut perm = ProjectMyPerms::from_level(0);
                if !p.is_private {
                    perm.read = true;
                }
                Some(perm)
            }
            (false, perm) => perm,
        };
        if viewer_id.is_none() {
            perms = Some(ProjectMyPerms::full());
        }
        responses.push(to_response(p, perms));
    }
    Ok(PaginationResponse::create(responses, total, pagination))
}

/// 项目详情(含当前用户权限位; 公开库强制 read=True)
pub async fn project_get_with_my_perms(
    state: &AppState,
    project_id: &str,
    user_id: &str,
) -> Result<Option<ProjectResponse>, AppError> {
    let Some(p) = dao::project_get(&state.db, project_id).await? else {
        return Ok(None);
    };
    let mut perms_map = compute_my_perms(state, user_id, &[project_id.to_string()]).await?;
    let mut perms = perms_map.remove(project_id);
    if let Some(perm) = perms.as_mut() {
        if !p.is_private {
            perm.read = true;
        }
    }
    Ok(Some(to_response(p, perms)))
}

// ==================== 项目成员服务 ====================

/// 保底校验: 目标是项目管理员时, 变更/移除后必须仍至少保留一个管理员
async fn assert_admin_remaining(state: &AppState, project_id: &str) -> Result<(), AppError> {
    let direct = dao::member_count_admins(&state.db, project_id).await?;
    let by_dept = dao::dept_count_admins(&state.db, project_id).await?;
    if direct + by_dept == 0 {
        return Err(AppError::conflict("必须至少保留一个项目管理员(project_admin)"));
    }
    Ok(())
}

/// 添加项目成员(角色校验 + invite 档位 + 去重)
pub async fn member_add(state: &AppState, req: ProjectMemberCreate, operator: &str) -> Result<String, AppError> {
    validate_role(&req.role).map_err(AppError::business)?;
    enforce_project_permission(state, operator, &req.project_id, "member", "invite").await?;
    if dao::member_get_by_user_and_project(&state.db, &req.user_id, &req.project_id)
        .await?
        .is_some()
    {
        return Err(AppError::conflict(format!(
            "用户 {} 已是项目 {} 的成员",
            req.user_id, req.project_id
        )));
    }
    let id = new_id();
    dao::member_add(
        &state.db,
        crate::do_::entity::project_member::ActiveModel {
            id: Set(id.clone()),
            user_id: Set(req.user_id),
            project_id: Set(req.project_id),
            role: Set(req.role),
            created_at: Set(Some(now_utc())),
            updated_at: Set(now_utc()),
        },
    )
    .await?;
    Ok(id)
}

/// 按ID获取成员记录(404 文案对齐 Python controller: "项目成员未找到")
pub async fn member_get(state: &AppState, member_id: &str) -> Result<ProjectMemberResponse, AppError> {
    let m = dao::member_get(&state.db, member_id)
        .await?
        .ok_or_else(|| AppError::not_found("项目成员未找到"))?;
    Ok(ProjectMemberResponse {
        id: m.id,
        user_id: m.user_id,
        project_id: m.project_id,
        role: m.role,
        created_at: m.created_at,
        updated_at: m.updated_at,
    })
}

/// 移除项目成员(remove 档位 + 管理员保底校验)
pub async fn member_delete(state: &AppState, member_id: &str, operator: &str) -> Result<(), AppError> {
    // 先查再鉴权(鉴权需要 project_id)
    let member = dao::member_get(&state.db, member_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {member_id} 的项目成员")))?;
    enforce_project_permission(state, operator, &member.project_id, "member", "remove").await?;
    dao::member_delete(&state.db, member_id).await?;
    if member.role == "project_admin" {
        assert_admin_remaining(state, &member.project_id).await?;
    }
    Ok(())
}

/// 变更成员角色(update 档位 + 角色校验 + 管理员保底)
pub async fn member_update(
    state: &AppState,
    member_id: &str,
    req: ProjectMemberUpdate,
    operator: &str,
) -> Result<(), AppError> {
    let member = dao::member_get(&state.db, member_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {member_id} 的项目成员")))?;
    let role = req
        .role
        .filter(|r| !r.is_empty())
        .unwrap_or_else(|| member.role.clone());
    validate_role(&role).map_err(AppError::business)?;
    enforce_project_permission(state, operator, &member.project_id, "member", "update").await?;
    dao::member_update_role(&state.db, member_id, &role).await?;
    // 目标原为/变更为 admin 时保底校验
    if member.role == "project_admin" || role == "project_admin" {
        assert_admin_remaining(state, &member.project_id).await?;
    }
    Ok(())
}

/// 项目成员列表(联 user 表; 可选角色/关键词过滤)
pub async fn member_list_by_project(
    state: &AppState,
    project_id: &str,
    role: Option<String>,
    user_keyword: Option<String>,
) -> Result<Vec<ProjectMemberWithUser>, AppError> {
    let rows = dao::member_list_by_project(&state.db, project_id, role.as_deref(), user_keyword.as_deref())
        .await?;
    Ok(rows
        .into_iter()
        .map(|row| ProjectMemberWithUser {
            member: ProjectMemberResponse {
                id: row.member.id,
                user_id: row.member.user_id,
                project_id: row.member.project_id,
                role: row.member.role,
                created_at: row.member.created_at,
                updated_at: row.member.updated_at,
            },
            username: row.username,
            nickname: row.nickname,
        })
        .collect())
}

/// 我参与的项目列表
pub async fn my_projects(state: &AppState, user_id: &str) -> Result<Vec<MyProjectResponse>, AppError> {
    let rows = dao::member_list_my_projects(&state.db, user_id).await?;
    Ok(rows
        .into_iter()
        .map(|row| MyProjectResponse {
            project_id: row.project.id,
            project_name: row.project.name,
            project_description: row.project.description,
            is_private: row.project.is_private,
            kb_category: row.project.kb_category,
            role: row.role,
            created_at: row.project.created_at,
        })
        .collect())
}

// ==================== 部门授权服务 ====================

/// 添加部门授权(角色校验 + invite 档位 + 项目/部门存在性 + 去重)
pub async fn dept_add(state: &AppState, req: ProjectDeptCreate, operator: &str) -> Result<String, AppError> {
    validate_role(&req.role).map_err(AppError::business)?;
    enforce_project_permission(state, operator, &req.project_id, "member", "invite").await?;
    dao::project_get(&state.db, &req.project_id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("项目不存在: {}", req.project_id)))?;
    let dept = module_authorization::do_::entity::dept::Entity::find_by_id(req.dept_id.clone())
        .one(&state.db)
        .await?
        .ok_or_else(|| AppError::not_found(format!("部门不存在: {}", req.dept_id)))?;
    if dao::dept_get_by_project_and_dept(&state.db, &req.project_id, &req.dept_id)
        .await?
        .is_some()
    {
        return Err(AppError::conflict(format!("部门 {} 已授权，可直接调整档位", dept.name)));
    }
    let id = new_id();
    dao::dept_add(
        &state.db,
        crate::do_::entity::project_dept::ActiveModel {
            id: Set(id.clone()),
            project_id: Set(req.project_id),
            dept_id: Set(req.dept_id),
            role: Set(req.role),
            created_at: Set(Some(now_utc())),
            updated_at: Set(now_utc()),
        },
    )
    .await?;
    Ok(id)
}

/// 按ID获取部门授权(404 文案对齐 Python controller: "部门授权未找到")
pub async fn dept_get(state: &AppState, id: &str) -> Result<ProjectDeptResponse, AppError> {
    let m = dao::dept_get(&state.db, id)
        .await?
        .ok_or_else(|| AppError::not_found("部门授权未找到"))?;
    Ok(ProjectDeptResponse {
        id: m.id,
        project_id: m.project_id,
        dept_id: m.dept_id,
        role: m.role,
        created_at: m.created_at,
        updated_at: m.updated_at,
    })
}

/// 移除部门授权(remove 档位 + 管理员保底)
pub async fn dept_delete(state: &AppState, id: &str, operator: &str) -> Result<(), AppError> {
    let dept_auth = dao::dept_get(&state.db, id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {id} 的部门授权")))?;
    enforce_project_permission(state, operator, &dept_auth.project_id, "member", "remove").await?;
    dao::dept_delete(&state.db, id).await?;
    if dept_auth.role == "project_admin" {
        assert_admin_remaining(state, &dept_auth.project_id).await?;
    }
    Ok(())
}

/// 变更部门授权档位(update 档位 + 管理员保底), 返回更新后的记录
pub async fn dept_update(
    state: &AppState,
    id: &str,
    req: ProjectDeptUpdate,
    operator: &str,
) -> Result<ProjectDeptResponse, AppError> {
    let dept_auth = dao::dept_get(&state.db, id)
        .await?
        .ok_or_else(|| AppError::not_found(format!("未找到ID为 {id} 的部门授权")))?;
    let role = req
        .role
        .filter(|r| !r.is_empty())
        .unwrap_or_else(|| dept_auth.role.clone());
    validate_role(&role).map_err(AppError::business)?;
    enforce_project_permission(state, operator, &dept_auth.project_id, "member", "update").await?;
    dao::dept_update_role(&state.db, id, &role).await?;
    if dept_auth.role == "project_admin" || role == "project_admin" {
        assert_admin_remaining(state, &dept_auth.project_id).await?;
    }
    dept_get(state, id).await
}

/// 项目部门授权列表(联 dept 表; 可选角色过滤)
pub async fn dept_list_by_project(
    state: &AppState,
    project_id: &str,
    role: Option<String>,
) -> Result<Vec<ProjectDeptWithDept>, AppError> {
    let rows = dao::dept_list_by_project(&state.db, project_id, role.as_deref()).await?;
    Ok(rows
        .into_iter()
        .map(|row| ProjectDeptWithDept {
            dept_auth: ProjectDeptResponse {
                id: row.dept_auth.id,
                project_id: row.dept_auth.project_id,
                dept_id: row.dept_auth.dept_id,
                role: row.dept_auth.role,
                created_at: row.dept_auth.created_at,
                updated_at: row.dept_auth.updated_at,
            },
            dept_name: row.dept_name,
        })
        .collect())
}
