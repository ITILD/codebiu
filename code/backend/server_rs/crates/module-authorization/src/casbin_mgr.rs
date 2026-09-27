//! Casbin 权限管理器(对齐 Python module_authorization/config/casbin_rule.py)
//!
//! - 自研 sea-orm adapter: casbin_rule 表(ptype/v0..v5)持久化, 容忍尾部空段
//! - 启动幂等补写默认策略(admin 穿透 + user 角色默认权限), 不同步重复声明
//! - 同步 role/permission 两张声明表(内置角色 upsert + 权限树按 code upsert)

use async_trait::async_trait;
use casbin::{Adapter, CoreApi, Enforcer, MgmtApi, Model, RbacApi};
use sea_orm::{
    ActiveModelTrait, ColumnTrait, DatabaseConnection, EntityTrait, QueryFilter, QueryOrder, Set,
};
use std::sync::OnceLock;
use tokio::sync::RwLock;

use crate::perms;
use crate::do_::entity::casbin_rule;

use super::services::perm_table::{self, PermissionRow};
use super::services::role_table::{self, RoleRow};

/// casbin 错误构造(adapter 层数据库异常统一包装)
fn casbin_err(e: impl std::fmt::Display) -> casbin::Error {
    casbin::Error::AdapterError(casbin::error::AdapterError(format!("{e}").into()))
}

// ############################# sea-orm Adapter #############################

/// casbin_rule 表适配器(规则行: id 自增主键, ptype + v0..v5)
#[derive(Clone)]
pub struct SeaOrmAdapter {
    db: DatabaseConnection,
}

impl SeaOrmAdapter {
    pub fn new(db: DatabaseConnection) -> Self {
        Self { db }
    }

    /// 规则行 → casbin 规则(截断尾部空段, 与 Python 侧语义一致)
    fn row_to_rule(row: &casbin_rule::Model) -> Option<(String, Vec<String>)> {
        let ptype = row.ptype.clone()?;
        let cells = [&row.v0, &row.v1, &row.v2, &row.v3, &row.v4, &row.v5];
        let mut rule: Vec<String> = Vec::new();
        for cell in cells {
            match cell {
                Some(v) => rule.push(v.clone()),
                None => break, // 尾部 NULL 视为段结束
            }
        }
        Some((ptype, rule))
    }

    /// 规则 → ActiveModel(不足 6 段以 NULL 填充尾部)
    fn rule_to_am(ptype: &str, rule: &[String]) -> casbin_rule::ActiveModel {
        let get = |i: usize| Set(rule.get(i).cloned());
        casbin_rule::ActiveModel {
            ptype: Set(Some(ptype.to_string())),
            v0: get(0),
            v1: get(1),
            v2: get(2),
            v3: get(3),
            v4: get(4),
            v5: get(5),
            ..Default::default()
        }
    }
}

#[async_trait]
impl Adapter for SeaOrmAdapter {
    /// 从库加载全部规则到模型(g 规则经 add_policy("g") 建立角色链接)
    async fn load_policy(&mut self, m: &mut dyn Model) -> casbin::Result<()> {
        let rows = casbin_rule::Entity::find()
            .order_by_asc(casbin_rule::Column::Id)
            .all(&self.db)
            .await
            .map_err(casbin_err)?;
        for row in &rows {
            if let Some((ptype, rule)) = Self::row_to_rule(row) {
                let sec = if ptype.starts_with('g') { "g" } else { "p" };
                m.add_policy(sec, &ptype, rule);
            }
        }
        Ok(())
    }

    /// 分段加载不支持(返回错误, 本项目不使用)
    async fn load_filtered_policy<'a>(
        &mut self,
        _m: &mut dyn Model,
        _f: casbin::Filter<'a>,
    ) -> casbin::Result<()> {
        Err(casbin_err("not implemented"))
    }

    /// 全量回写(先取模型快照, 清库后按模型重写)
    async fn save_policy(&mut self, m: &mut dyn Model) -> casbin::Result<()> {
        let p_rules = m.get_policy("p", "p");
        let g_rules = m.get_policy("g", "g");
        casbin_rule::Entity::delete_many()
            .exec(&self.db)
            .await
            .map_err(casbin_err)?;
        let mut models: Vec<casbin_rule::ActiveModel> = Vec::new();
        for rule in p_rules {
            models.push(Self::rule_to_am("p", &rule));
        }
        for rule in g_rules {
            models.push(Self::rule_to_am("g", &rule));
        }
        if !models.is_empty() {
            casbin_rule::Entity::insert_many(models)
                .exec(&self.db)
                .await
                .map_err(casbin_err)?;
        }
        Ok(())
    }

    async fn clear_policy(&mut self) -> casbin::Result<()> {
        casbin_rule::Entity::delete_many()
            .exec(&self.db)
            .await
            .map_err(casbin_err)?;
        Ok(())
    }

    fn is_filtered(&self) -> bool {
        false
    }

    /// 单条写入(幂等性由调用方 enforcer 内存层保证)
    async fn add_policy(
        &mut self,
        sec: &str,
        ptype: &str,
        rule: Vec<String>,
    ) -> casbin::Result<bool> {
        let _ = sec;
        Self::rule_to_am(ptype, &rule)
            .insert(&self.db)
            .await
            .map_err(casbin_err)?;
        Ok(true)
    }

    async fn add_policies(
        &mut self,
        sec: &str,
        ptype: &str,
        rules: Vec<Vec<String>>,
    ) -> casbin::Result<bool> {
        if rules.is_empty() {
            return Ok(true);
        }
        let _ = sec;
        let models: Vec<casbin_rule::ActiveModel> =
            rules.iter().map(|r| Self::rule_to_am(ptype, r)).collect();
        casbin_rule::Entity::insert_many(models)
            .exec(&self.db)
            .await
            .map_err(casbin_err)?;
        Ok(true)
    }

    /// 按全字段精确删除(仅匹配 rule 提供的段)
    async fn remove_policy(
        &mut self,
        _sec: &str,
        ptype: &str,
        rule: Vec<String>,
    ) -> casbin::Result<bool> {
        let mut delete = casbin_rule::Entity::delete_many()
            .filter(casbin_rule::Column::Ptype.eq(ptype));
        for (i, value) in rule.iter().enumerate() {
            let col = match i {
                0 => casbin_rule::Column::V0,
                1 => casbin_rule::Column::V1,
                2 => casbin_rule::Column::V2,
                3 => casbin_rule::Column::V3,
                4 => casbin_rule::Column::V4,
                _ => casbin_rule::Column::V5,
            };
            delete = delete.filter(col.eq(value));
        }
        let result = delete.exec(&self.db).await.map_err(casbin_err)?;
        Ok(result.rows_affected > 0)
    }

    async fn remove_policies(
        &mut self,
        sec: &str,
        ptype: &str,
        rules: Vec<Vec<String>>,
    ) -> casbin::Result<bool> {
        let mut any = false;
        for rule in rules {
            if self.remove_policy(sec, ptype, rule).await? {
                any = true;
            }
        }
        Ok(any)
    }

    /// 条件删除(field_index 起始, 非空值参与过滤)
    async fn remove_filtered_policy(
        &mut self,
        _sec: &str,
        ptype: &str,
        field_index: usize,
        field_values: Vec<String>,
    ) -> casbin::Result<bool> {
        let mut delete = casbin_rule::Entity::delete_many()
            .filter(casbin_rule::Column::Ptype.eq(ptype));
        for (offset, value) in field_values.iter().enumerate() {
            if value.is_empty() {
                continue; // 空串视为通配
            }
            let col = match field_index + offset {
                0 => casbin_rule::Column::V0,
                1 => casbin_rule::Column::V1,
                2 => casbin_rule::Column::V2,
                3 => casbin_rule::Column::V3,
                4 => casbin_rule::Column::V4,
                _ => casbin_rule::Column::V5,
            };
            delete = delete.filter(col.eq(value));
        }
        let result = delete.exec(&self.db).await.map_err(casbin_err)?;
        Ok(result.rows_affected > 0)
    }
}

// ############################# AuthManager #############################

/// 全局权限管理器(enforcer 可选: 未初始化时拒绝所有请求)
pub struct AuthManager {
    inner: RwLock<Option<Enforcer>>,
}

static AUTH: OnceLock<AuthManager> = OnceLock::new();

/// 全局单例访问
pub fn auth() -> &'static AuthManager {
    AUTH.get_or_init(|| AuthManager { inner: RwLock::new(None) })
}

/// 内置角色(role 表中始终存在, 策略随声明维护)
pub const BUILTIN_ROLES: &[RoleRow] = &[
    RoleRow {
        name: "系统管理员",
        role_key: "admin",
        description: "全局管理员,拥有系统全部权限",
        sort: 1,
    },
    RoleRow {
        name: "普通用户",
        role_key: "user",
        description: "新注册用户默认角色,拥有各模块声明的基础权限",
        sort: 2,
    },
];

impl AuthManager {
    /// 幂等初始化(建 enforcer → 补写默认策略 → 同步角色/权限声明表)
    ///
    /// 失败返回 false 且 enforcer 保持未初始化(请求期全部拒绝)。
    pub async fn init(&self, db: DatabaseConnection) -> bool {
        let mut guard = self.inner.write().await;
        if guard.is_some() {
            return true;
        }
        match self.init_inner(db).await {
            Ok(enforcer) => {
                *guard = Some(enforcer);
                true
            }
            Err(e) => {
                tracing::error!("初始化默认权限策略失败: {e}");
                false
            }
        }
    }

    async fn init_inner(&self, db: DatabaseConnection) -> Result<Enforcer, String> {
        // rbac_model.conf 位于 server_rs 根(与 Python 侧同一模型文件)
        let adapter = SeaOrmAdapter::new(db.clone());
        let mut enforcer = Enforcer::new("rbac_model.conf", adapter)
            .await
            .map_err(|e| format!("enforcer 构建失败: {e}"))?;

        // ===== 批量查缺: 现有 p 规则与期望集合比对, 缺失一次性补写 =====
        let existing: std::collections::HashSet<Vec<String>> =
            enforcer.get_policy().into_iter().collect();
        let mut expected: std::collections::HashSet<Vec<String>> =
            std::collections::HashSet::new();
        // 全局策略: 超管角色穿透一切
        expected.insert(vec!["admin".into(), "*".into(), "*".into(), "*".into()]);
        // 内置 user 角色策略 = 各模块 default_policies 合并
        for (dom, obj, act) in perms::default_user_policies() {
            expected.insert(vec!["user".into(), dom, obj, act]);
        }
        let missing: Vec<Vec<String>> = expected
            .difference(&existing)
            .cloned()
            .collect();
        if missing.is_empty() {
            tracing::info!("默认权限策略完整,无需补写");
        } else {
            let count = missing.len();
            enforcer
                .add_policies(missing)
                .await
                .map_err(|e| format!("策略补写失败: {e}"))?;
            tracing::info!("策略批量初始化完成,新增 {count} 条");
        }

        // 同步角色表/权限表(失败不影响 casbin)
        if let Err(e) = self.sync_permission_tables(&db).await {
            tracing::error!("同步角色/权限表失败: {e}");
        }
        let modules: Vec<&str> = perms::get_all().iter().map(|d| d.module).collect();
        tracing::info!("已注册权限声明模块: {modules:?}");
        Ok(enforcer)
    }

    /// 将注册中心声明幂等同步到 role 表与 permission 表
    async fn sync_permission_tables(&self, db: &DatabaseConnection) -> Result<(), String> {
        // 角色表: upsert 内置角色(不动 data_scope/is_active 等可编辑字段)
        for role in BUILTIN_ROLES {
            role_table::upsert_builtin(db, role).await.map_err(|e| e.to_string())?;
        }
        // 权限表: 模块根节点(M) + 递归子树, 按 code upsert
        for define in perms::get_all() {
            let root = PermissionRow {
                name: define.name,
                code: define.module,
                menu_type: "M",
                description: define.description,
                path: None,
                icon: define.icon,
                order_num: define.order_num,
                visible: true,
                parent_id: "0".to_string(),
            };
            let root_id = perm_table::upsert(db, &root)
                .await
                .map_err(|e| e.to_string())?;
            sync_children(db, define.nodes, &root_id).await?;
        }
        Ok(())
    }

    // #################### 只读操作 ####################

    /// 是否已初始化
    pub async fn ready(&self) -> bool {
        self.inner.read().await.is_some()
    }

    /// enforcer 判定(未初始化拒绝所有)
    pub async fn enforce(&self, user_id: &str, dom: &str, obj: &str, act: &str) -> bool {
        let guard = self.inner.read().await;
        match guard.as_ref() {
            Some(enforcer) => match enforcer.enforce((user_id, dom, obj, act)) {
                Ok(ok) => ok,
                Err(e) => {
                    tracing::error!("权限检查异常: {e}");
                    false
                }
            },
            None => {
                tracing::warn!("Casbin enforcer 未初始化,拒绝所有请求");
                false
            }
        }
    }

    /// 全局管理员判定(全局域 "*" 的 admin 绑定)
    pub async fn is_global_admin(&self, user_id: &str) -> bool {
        self.has_grouping_policy(user_id, "admin", "*").await
    }

    /// 分组规则存在性判定(g user role dom)
    pub async fn has_grouping_policy(&self, user_id: &str, role: &str, dom: &str) -> bool {
        let guard = self.inner.read().await;
        match guard.as_ref() {
            Some(enforcer) => {
                enforcer.has_grouping_policy(vec![user_id.to_string(), role.to_string(), dom.to_string()])
            }
            None => false,
        }
    }

    /// 用户在指定域的角色列表(dom=None 返回全部域)
    pub async fn get_roles_for_user(&self, user_id: &str, dom: Option<&str>) -> Vec<String> {
        let guard = self.inner.read().await;
        match guard.as_ref() {
            Some(enforcer) => enforcer.get_roles_for_user(user_id, dom),
            None => Vec::new(),
        }
    }

    /// 全部 p 规则(可选 dom 过滤, "*" 表示不过滤)
    pub async fn get_policies(&self, dom: Option<&str>) -> Vec<Vec<String>> {
        let guard = self.inner.read().await;
        match guard.as_ref() {
            Some(enforcer) => match dom {
                Some(d) if d != "*" => enforcer.get_filtered_policy(1, vec![d.to_string()]),
                _ => enforcer.get_policy(),
            },
            None => Vec::new(),
        }
    }

    /// 全部 g 规则(可选 dom 过滤)
    pub async fn get_grouping_policies(&self, dom: Option<&str>) -> Vec<Vec<String>> {
        let guard = self.inner.read().await;
        match guard.as_ref() {
            Some(enforcer) => match dom {
                Some(d) if d != "*" => {
                    enforcer.get_filtered_grouping_policy(2, vec![d.to_string()])
                }
                _ => enforcer.get_grouping_policy(),
            },
            None => Vec::new(),
        }
    }

    /// 指定角色在域内的权限策略(返回 (dom, obj, act) 列表)
    pub async fn get_role_policies(&self, role_key: &str, dom: &str) -> Vec<Vec<String>> {
        self.get_policies(None)
            .await
            .into_iter()
            .filter(|p| p.len() >= 4 && p[0] == role_key && (dom == "*" || p[1] == dom))
            .collect()
    }

    // #################### 写操作 ####################

    /// 添加策略 p(rule: [sub, dom, obj, act]); 已存在返回 false
    pub async fn add_policy(&self, rule: Vec<String>) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        if e.has_policy(rule.clone()) {
            return Ok(false);
        }
        e.add_policy(rule).await.map_err(|er| er.to_string())
    }

    /// 删除策略 p(全字段匹配)
    pub async fn remove_policy(&self, rule: Vec<String>) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        e.remove_policy(rule).await.map_err(|er| er.to_string())
    }

    /// 条件删除 p 规则(field_index 起始, 空串通配)
    pub async fn remove_filtered_policy(
        &self,
        field_index: usize,
        field_values: Vec<String>,
    ) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        e.remove_filtered_policy(field_index, field_values)
            .await
            .map_err(|er| er.to_string())
    }

    /// 添加角色绑定 g(user, role, dom)
    pub async fn add_grouping_policy(&self, rule: Vec<String>) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        if e.has_grouping_policy(rule.clone()) {
            return Ok(false);
        }
        e.add_grouping_policy(rule).await.map_err(|er| er.to_string())
    }

    /// 删除角色绑定 g(全字段匹配)
    pub async fn remove_grouping_policy(&self, rule: Vec<String>) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        e.remove_grouping_policy(rule).await.map_err(|er| er.to_string())
    }

    /// 条件删除 g 规则
    pub async fn remove_filtered_grouping_policy(
        &self,
        field_index: usize,
        field_values: Vec<String>,
    ) -> Result<bool, String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        e.remove_filtered_grouping_policy(field_index, field_values)
            .await
            .map_err(|er| er.to_string())
    }

    /// 批量写入策略(逐条落库, 返回实际新增条数)
    pub async fn add_policies(&self, rules: Vec<Vec<String>>) -> Result<usize, String> {
        let mut added = 0;
        for rule in rules {
            if self.add_policy(rule).await? {
                added += 1;
            }
        }
        Ok(added)
    }

    /// 从库重载策略
    pub async fn reload_policy(&self) -> Result<(), String> {
        let mut guard = self.inner.write().await;
        let e = guard
            .as_mut()
            .ok_or_else(|| "Casbin enforcer 未初始化".to_string())?;
        e.load_policy().await.map_err(|er| er.to_string())
    }
}

/// 递归同步权限子树(深度优先, parent_id 关联)
async fn sync_children(
    db: &DatabaseConnection,
    nodes: &'static [perms::PermNode],
    parent_id: &str,
) -> Result<(), String> {
    for node in nodes {
        let row = PermissionRow {
            name: node.name,
            code: node.code,
            menu_type: node.menu_type,
            description: node.description,
            path: node.path,
            icon: node.icon,
            order_num: node.order_num,
            visible: node.visible,
            parent_id: parent_id.to_string(),
        };
        let node_id = perm_table::upsert(db, &row).await.map_err(|e| e.to_string())?;
        if !node.children.is_empty() {
            Box::pin(sync_children(db, node.children, &node_id)).await?;
        }
    }
    Ok(())
}
