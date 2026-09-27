//! 项目/成员/部门授权 DAO(sea-orm 查询, 对齐 Python module_rag/dao/project.py、
//! project_member.py、project_dept.py)

use sea_orm::{
    ActiveModelTrait, ColumnTrait, Condition, DatabaseConnection, DbErr, EntityTrait,
    IntoActiveModel, JoinType, PaginatorTrait, QueryFilter, QueryOrder, QuerySelect, QueryTrait,
    RelationTrait, Set,
};

use crate::do_::entity::{project, project_dept, project_member};
use module_authorization::do_::entity::{dept, user};

// ==================== 项目 ====================

/// 按ID获取项目
pub async fn project_get(db: &DatabaseConnection, id: &str) -> Result<Option<project::Model>, DbErr> {
    project::Entity::find_by_id(id.to_owned()).one(db).await
}

/// 私有库可见性条件(公开 OR 创建者 OR 直连成员 OR 部门授权链命中)
fn visibility_condition(viewer_id: &str, dept_chain: &[String]) -> Condition {
    Condition::any()
        .add(project::Column::IsPrivate.eq(false))
        .add(project::Column::CreatedBy.eq(viewer_id))
        .add(
            project::Column::Id.in_subquery(
                project_member::Entity::find()
                    .select_only()
                    .column(project_member::Column::ProjectId)
                    .filter(project_member::Column::UserId.eq(viewer_id))
                    .into_query(),
            ),
        )
        .add(
            project::Column::Id.in_subquery(
                project_dept::Entity::find()
                    .select_only()
                    .column(project_dept::Column::ProjectId)
                    .filter(project_dept::Column::DeptId.is_in(dept_chain.to_vec()))
                    .into_query(),
            ),
        )
}

/// 项目列表/计数共用过滤条件(name/kb_category/is_private/可见性)
fn project_filter(
    name: Option<&str>,
    kb_category: Option<&str>,
    is_private: Option<bool>,
    viewer_id: Option<&str>,
    dept_chain: &[String],
) -> Condition {
    let mut cond = Condition::all();
    if let Some(n) = name.filter(|v| !v.is_empty()) {
        cond = cond.add(project::Column::Name.contains(n));
    }
    if let Some(c) = kb_category {
        cond = cond.add(project::Column::KbCategory.eq(c));
    }
    if let Some(p) = is_private {
        cond = cond.add(project::Column::IsPrivate.eq(p));
    }
    if let Some(viewer) = viewer_id {
        cond = cond.add(visibility_condition(viewer, dept_chain));
    }
    cond
}

/// 分页查询项目列表(按创建时间倒序)
pub async fn project_list_paged(
    db: &DatabaseConnection,
    page: i64,
    size: i64,
    name: Option<&str>,
    kb_category: Option<&str>,
    is_private: Option<bool>,
    viewer_id: Option<&str>,
    dept_chain: &[String],
) -> Result<Vec<project::Model>, DbErr> {
    project::Entity::find()
        .filter(project_filter(name, kb_category, is_private, viewer_id, dept_chain))
        .order_by_desc(project::Column::CreatedAt)
        .offset(((page - 1).max(0) * size) as u64)
        .limit(size.max(0) as u64)
        .all(db)
        .await
}

/// 项目计数(与列表同过滤口径)
pub async fn project_count(
    db: &DatabaseConnection,
    name: Option<&str>,
    kb_category: Option<&str>,
    is_private: Option<bool>,
    viewer_id: Option<&str>,
    dept_chain: &[String],
) -> Result<i64, DbErr> {
    project::Entity::find()
        .filter(project_filter(name, kb_category, is_private, viewer_id, dept_chain))
        .count(db)
        .await
        .map(|c| c as i64)
}

/// 新增项目
pub async fn project_add(
    db: &DatabaseConnection,
    am: project::ActiveModel,
) -> Result<project::Model, DbErr> {
    am.insert(db).await
}

/// 更新项目(仅非 None 字段)
pub async fn project_update(
    db: &DatabaseConnection,
    id: &str,
    name: Option<String>,
    description: Option<Option<String>>,
    is_private: Option<bool>,
    kb_category: Option<String>,
    root_entry_id: Option<String>,
) -> Result<(), DbErr> {
    let Some(existing) = project::Entity::find_by_id(id.to_owned()).one(db).await? else {
        return Ok(());
    };
    let mut am = existing.into_active_model();
    if let Some(v) = name {
        am.name = Set(v);
    }
    if let Some(v) = description {
        am.description = Set(v);
    }
    if let Some(v) = is_private {
        am.is_private = Set(v);
    }
    if let Some(v) = kb_category {
        am.kb_category = Set(v);
    }
    if let Some(v) = root_entry_id {
        am.root_entry_id = Set(Some(v));
    }
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await?;
    Ok(())
}

/// 删除项目
pub async fn project_delete(db: &DatabaseConnection, id: &str) -> Result<(), DbErr> {
    project::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    Ok(())
}

/// 按项目根文件夹条目ID批量查项目(下载授权判定用)
pub async fn project_get_by_root_entry_ids(
    db: &DatabaseConnection,
    entry_ids: &[String],
) -> Result<Vec<project::Model>, DbErr> {
    if entry_ids.is_empty() {
        return Ok(Vec::new());
    }
    project::Entity::find()
        .filter(project::Column::RootEntryId.is_in(entry_ids.to_vec()))
        .all(db)
        .await
}

// ==================== 项目成员 ====================

/// 按ID获取成员
pub async fn member_get(db: &DatabaseConnection, id: &str) -> Result<Option<project_member::Model>, DbErr> {
    project_member::Entity::find_by_id(id.to_owned()).one(db).await
}

/// 按(用户, 项目)获取成员记录
pub async fn member_get_by_user_and_project(
    db: &DatabaseConnection,
    user_id: &str,
    project_id: &str,
) -> Result<Option<project_member::Model>, DbErr> {
    project_member::Entity::find()
        .filter(
            Condition::all()
                .add(project_member::Column::UserId.eq(user_id))
                .add(project_member::Column::ProjectId.eq(project_id)),
        )
        .one(db)
        .await
}

/// 新增成员
pub async fn member_add(
    db: &DatabaseConnection,
    am: project_member::ActiveModel,
) -> Result<project_member::Model, DbErr> {
    am.insert(db).await
}

/// 更新成员角色
pub async fn member_update_role(
    db: &DatabaseConnection,
    id: &str,
    role: &str,
) -> Result<(), DbErr> {
    let Some(existing) = project_member::Entity::find_by_id(id.to_owned()).one(db).await? else {
        return Ok(());
    };
    let mut am = existing.into_active_model();
    am.role = Set(role.to_string());
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await?;
    Ok(())
}

/// 删除成员
pub async fn member_delete(db: &DatabaseConnection, id: &str) -> Result<(), DbErr> {
    project_member::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    Ok(())
}

/// 成员列表项(成员记录 + 联查用户名/昵称)
pub struct MemberRow {
    pub member: project_member::Model,
    pub username: Option<String>,
    pub nickname: Option<String>,
}

/// 项目成员列表(联 user 表; 可选角色/用户名或昵称关键词过滤, 创建时间倒序)
pub async fn member_list_by_project(
    db: &DatabaseConnection,
    project_id: &str,
    role: Option<&str>,
    user_keyword: Option<&str>,
) -> Result<Vec<MemberRow>, DbErr> {
    let mut select = project_member::Entity::find()
        .filter(project_member::Column::ProjectId.eq(project_id))
        .join(JoinType::LeftJoin, project_member::Relation::User.def())
        .select_only()
        .column(project_member::Column::Id)
        .column(project_member::Column::UserId)
        .column(project_member::Column::ProjectId)
        .column(project_member::Column::Role)
        .column(project_member::Column::CreatedAt)
        .column(project_member::Column::UpdatedAt)
        .column_as(user::Column::Username, "m_username")
        .column_as(user::Column::Nickname, "m_nickname");
    if let Some(r) = role {
        select = select.filter(project_member::Column::Role.eq(r));
    }
    if let Some(k) = user_keyword.filter(|v| !v.is_empty()) {
        select = select.filter(
            Condition::any()
                .add(user::Column::Username.contains(k))
                .add(user::Column::Nickname.contains(k)),
        );
    }
    let rows = select
        .order_by_desc(project_member::Column::CreatedAt)
        .into_tuple::<(
            String,
            String,
            String,
            String,
            Option<sea_orm::prelude::DateTimeWithTimeZone>,
            sea_orm::prelude::DateTimeWithTimeZone,
            Option<String>,
            Option<String>,
        )>()
        .all(db)
        .await?;
    Ok(rows
        .into_iter()
        .map(
            |(id, user_id, project_id, role, created_at, updated_at, username, nickname)| MemberRow {
                member: project_member::Model {
                    id,
                    user_id,
                    project_id,
                    role,
                    created_at,
                    updated_at,
                },
                username,
                nickname,
            },
        )
        .collect())
}

/// 我参与的项目行(成员档位 + 项目元数据)
pub struct MyProjectRow {
    pub project: project::Model,
    pub role: String,
}

/// 我参与的项目列表(成员表联项目表, 创建时间倒序; scope 过滤在服务层做)
pub async fn member_list_my_projects(
    db: &DatabaseConnection,
    user_id: &str,
) -> Result<Vec<MyProjectRow>, DbErr> {
    let select = project_member::Entity::find()
        .filter(project_member::Column::UserId.eq(user_id))
        .join(JoinType::InnerJoin, project_member::Relation::Project.def())
        .select_only()
        .column(project::Column::Id)
        .column(project::Column::Name)
        .column(project::Column::Description)
        .column(project::Column::IsPrivate)
        .column(project::Column::KbCategory)
        .column(project::Column::CreatedBy)
        .column(project::Column::RootEntryId)
        .column(project::Column::CreatedAt)
        .column(project::Column::UpdatedAt)
        .column_as(project_member::Column::Role, "m_role");
    let rows = select
        .order_by_desc(project::Column::CreatedAt)
        .into_tuple::<(
            String,
            String,
            Option<String>,
            bool,
            String,
            String,
            Option<String>,
            Option<sea_orm::prelude::DateTimeWithTimeZone>,
            sea_orm::prelude::DateTimeWithTimeZone,
            String,
        )>()
        .all(db)
        .await?;
    Ok(rows
        .into_iter()
        .map(|(id, name, description, is_private, kb_category, created_by, root_entry_id, created_at, updated_at, role)| {
            MyProjectRow {
                project: project::Model {
                    id,
                    name,
                    description,
                    is_private,
                    kb_category,
                    created_by,
                    root_entry_id,
                    created_at,
                    updated_at,
                },
                role,
            }
        })
        .collect())
}

/// 项目直连管理员计数(联 user 表仅计在职用户)
pub async fn member_count_admins(db: &DatabaseConnection, project_id: &str) -> Result<i64, DbErr> {
    project_member::Entity::find()
        .filter(
            Condition::all()
                .add(project_member::Column::ProjectId.eq(project_id))
                .add(project_member::Column::Role.eq("project_admin")),
        )
        .join(JoinType::InnerJoin, project_member::Relation::User.def())
        .filter(user::Column::IsActive.eq(true))
        .count(db)
        .await
        .map(|c| c as i64)
}

/// 项目删除全部成员记录, 返回删除数
pub async fn member_delete_by_project(db: &DatabaseConnection, project_id: &str) -> Result<u64, DbErr> {
    let res = project_member::Entity::delete_many()
        .filter(project_member::Column::ProjectId.eq(project_id))
        .exec(db)
        .await?;
    Ok(res.rows_affected)
}

/// (用户, 项目列表) → 各项目直连角色(权限位批量计算用)
pub async fn member_list_roles_by_projects(
    db: &DatabaseConnection,
    user_id: &str,
    project_ids: &[String],
) -> Result<Vec<(String, String)>, DbErr> {
    if project_ids.is_empty() {
        return Ok(Vec::new());
    }
    project_member::Entity::find()
        .filter(
            Condition::all()
                .add(project_member::Column::UserId.eq(user_id))
                .add(project_member::Column::ProjectId.is_in(project_ids.to_vec())),
        )
        .all(db)
        .await
        .map(|rows| rows.into_iter().map(|m| (m.project_id, m.role)).collect())
}

// ==================== 部门授权 ====================

/// 按ID获取部门授权
pub async fn dept_get(db: &DatabaseConnection, id: &str) -> Result<Option<project_dept::Model>, DbErr> {
    project_dept::Entity::find_by_id(id.to_owned()).one(db).await
}

/// 按(项目, 部门)获取授权记录
pub async fn dept_get_by_project_and_dept(
    db: &DatabaseConnection,
    project_id: &str,
    dept_id: &str,
) -> Result<Option<project_dept::Model>, DbErr> {
    project_dept::Entity::find()
        .filter(
            Condition::all()
                .add(project_dept::Column::ProjectId.eq(project_id))
                .add(project_dept::Column::DeptId.eq(dept_id)),
        )
        .one(db)
        .await
}

/// 新增部门授权
pub async fn dept_add(
    db: &DatabaseConnection,
    am: project_dept::ActiveModel,
) -> Result<project_dept::Model, DbErr> {
    am.insert(db).await
}

/// 更新部门授权档位
pub async fn dept_update_role(db: &DatabaseConnection, id: &str, role: &str) -> Result<(), DbErr> {
    let Some(existing) = project_dept::Entity::find_by_id(id.to_owned()).one(db).await? else {
        return Ok(());
    };
    let mut am = existing.into_active_model();
    am.role = Set(role.to_string());
    am.updated_at = Set(chrono::Utc::now().into());
    am.update(db).await?;
    Ok(())
}

/// 删除部门授权
pub async fn dept_delete(db: &DatabaseConnection, id: &str) -> Result<(), DbErr> {
    project_dept::Entity::delete_by_id(id.to_owned()).exec(db).await?;
    Ok(())
}

/// 部门授权列表项(授权记录 + 联查部门名)
pub struct DeptAuthRow {
    pub dept_auth: project_dept::Model,
    pub dept_name: Option<String>,
}

/// 项目部门授权列表(联 dept 表; 可选角色过滤, 创建时间倒序)
pub async fn dept_list_by_project(
    db: &DatabaseConnection,
    project_id: &str,
    role: Option<&str>,
) -> Result<Vec<DeptAuthRow>, DbErr> {
    let mut select = project_dept::Entity::find()
        .filter(project_dept::Column::ProjectId.eq(project_id))
        .join(JoinType::LeftJoin, project_dept::Relation::Dept.def())
        .select_only()
        .column(project_dept::Column::Id)
        .column(project_dept::Column::ProjectId)
        .column(project_dept::Column::DeptId)
        .column(project_dept::Column::Role)
        .column(project_dept::Column::CreatedAt)
        .column(project_dept::Column::UpdatedAt)
        .column_as(dept::Column::Name, "d_name");
    if let Some(r) = role {
        select = select.filter(project_dept::Column::Role.eq(r));
    }
    let rows = select
        .order_by_desc(project_dept::Column::CreatedAt)
        .into_tuple::<(
            String,
            String,
            String,
            String,
            Option<sea_orm::prelude::DateTimeWithTimeZone>,
            sea_orm::prelude::DateTimeWithTimeZone,
            Option<String>,
        )>()
        .all(db)
        .await?;
    Ok(rows
        .into_iter()
        .map(|(id, project_id, dept_id, role, created_at, updated_at, dept_name)| DeptAuthRow {
            dept_auth: project_dept::Model { id, project_id, dept_id, role, created_at, updated_at },
            dept_name,
        })
        .collect())
}

/// 项目部门授权管理员计数(档位校验用)
pub async fn dept_count_admins(db: &DatabaseConnection, project_id: &str) -> Result<i64, DbErr> {
    project_dept::Entity::find()
        .filter(
            Condition::all()
                .add(project_dept::Column::ProjectId.eq(project_id))
                .add(project_dept::Column::Role.eq("project_admin")),
        )
        .count(db)
        .await
        .map(|c| c as i64)
}

/// 项目删除全部部门授权记录, 返回删除数
pub async fn dept_delete_by_project(db: &DatabaseConnection, project_id: &str) -> Result<u64, DbErr> {
    let res = project_dept::Entity::delete_many()
        .filter(project_dept::Column::ProjectId.eq(project_id))
        .exec(db)
        .await?;
    Ok(res.rows_affected)
}

/// (部门链, 项目列表) → 各项目部门授权最高角色(权限位批量计算用)
pub async fn dept_list_roles_by_projects(
    db: &DatabaseConnection,
    dept_chain: &[String],
    project_ids: &[String],
) -> Result<Vec<(String, String)>, DbErr> {
    if dept_chain.is_empty() || project_ids.is_empty() {
        return Ok(Vec::new());
    }
    project_dept::Entity::find()
        .filter(
            Condition::all()
                .add(project_dept::Column::DeptId.is_in(dept_chain.to_vec()))
                .add(project_dept::Column::ProjectId.is_in(project_ids.to_vec())),
        )
        .all(db)
        .await
        .map(|rows| rows.into_iter().map(|m| (m.project_id, m.role)).collect())
}

/// (项目, 部门链) → 命中的授权档位列表(部门链级联鉴权用)
pub async fn dept_list_roles_by_dept_ids(
    db: &DatabaseConnection,
    project_id: &str,
    dept_chain: &[String],
) -> Result<Vec<String>, DbErr> {
    if dept_chain.is_empty() {
        return Ok(Vec::new());
    }
    project_dept::Entity::find()
        .filter(
            Condition::all()
                .add(project_dept::Column::ProjectId.eq(project_id))
                .add(project_dept::Column::DeptId.is_in(dept_chain.to_vec())),
        )
        .all(db)
        .await
        .map(|rows| rows.into_iter().map(|m| m.role).collect())
}
