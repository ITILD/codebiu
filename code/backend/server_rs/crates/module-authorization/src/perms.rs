//! 权限注册中心(对齐 Python module_authorization/config/registry.py)
//!
//! 各模块声明自己的权限树(ModulePermissionDefine), 启动时由 casbin_mgr 幂等同步到:
//! 1. casbin 策略表(p: 角色-域-资源-动作) 2. role 表 3. permission 表
//!
//! 权限码约定: "模块"(M目录) / "模块:资源"(C菜单) / "模块:资源:动作"(F按钮)

use std::collections::HashSet;
use std::sync::{Mutex, OnceLock};

/// 权限树节点声明(目录/菜单/按钮)
pub struct PermNode {
    pub name: &'static str,
    pub code: &'static str,
    /// 菜单类型: M=目录 C=菜单 F=按钮
    pub menu_type: &'static str,
    pub description: Option<&'static str>,
    /// 前端路由路径(菜单节点)
    pub path: Option<&'static str>,
    pub icon: Option<&'static str>,
    pub order_num: i32,
    pub visible: bool,
    pub children: &'static [PermNode],
}

impl PermNode {
    /// 深度优先遍历自身与全部子孙节点
    pub fn walk<'a>(&'a self, out: &mut Vec<&'a PermNode>) {
        out.push(self);
        for child in self.children {
            child.walk(out);
        }
    }
}

/// 模块权限声明(一个业务模块的完整权限定义)
pub struct ModulePermissionDefine {
    /// 模块域名, 同时是权限树根节点 code
    pub module: &'static str,
    pub name: &'static str,
    pub icon: Option<&'static str>,
    pub order_num: i32,
    pub description: Option<&'static str>,
    /// 模块权限树(不含模块根节点)
    pub nodes: &'static [PermNode],
    /// 新用户默认权限(并入内置 user 角色), 每项为 (域, 资源, 动作)
    pub default_policies: &'static [(&'static str, &'static str, &'static str)],
}

/// 解析按钮级权限码为 (dom, obj, act); 非三段码返回 None
pub fn parse_perm_code(code: &str) -> Option<(&str, &str, &str)> {
    let parts: Vec<&str> = code.split(':').collect();
    if parts.len() != 3 || parts.iter().any(|p| p.is_empty()) {
        return None;
    }
    Some((parts[0], parts[1], parts[2]))
}

/// 全局注册中心(启动期注册, 运行期只读)
struct PermissionRegistry {
    defines: Mutex<Vec<&'static ModulePermissionDefine>>,
}

static REGISTRY: OnceLock<PermissionRegistry> = OnceLock::new();

fn registry() -> &'static PermissionRegistry {
    REGISTRY.get_or_init(|| PermissionRegistry { defines: Mutex::new(Vec::new()) })
}

/// 注册模块权限声明(重复注册以最新声明为准: 按模块名去重覆盖)
pub fn register(define: &'static ModulePermissionDefine) {
    let mut defines = registry().defines.lock().expect("注册锁");
    if let Some(slot) = defines.iter_mut().find(|d| d.module == define.module) {
        *slot = define;
    } else {
        defines.push(define);
    }
}

/// 全部模块声明(按 order_num 排序)
pub fn get_all() -> Vec<&'static ModulePermissionDefine> {
    let mut defines = registry().defines.lock().expect("注册锁").clone();
    defines.sort_by_key(|d| d.order_num);
    defines
}

/// 按模块名获取声明
pub fn get(module: &str) -> Option<&'static ModulePermissionDefine> {
    get_all().into_iter().find(|d| d.module == module)
}

/// 遍历全部权限树, 收集按钮级节点对应的 (dom, obj, act)(可分配权限集合)
pub fn iter_node_policies() -> Vec<(String, String, String)> {
    let mut policies = Vec::new();
    for define in get_all() {
        let mut nodes = Vec::new();
        for node in define.nodes {
            node.walk(&mut nodes);
        }
        for leaf in nodes {
            if let Some((dom, obj, act)) = parse_perm_code(leaf.code) {
                policies.push((dom.to_string(), obj.to_string(), act.to_string()));
            }
        }
    }
    policies
}

/// 收集全部模块声明的新用户默认权限(合并为内置 user 角色策略, 去重)
pub fn default_user_policies() -> Vec<(String, String, String)> {
    let mut seen: HashSet<(String, String, String)> = HashSet::new();
    let mut policies = Vec::new();
    for define in get_all() {
        for (dom, obj, act) in define.default_policies {
            let key = (dom.to_string(), obj.to_string(), act.to_string());
            if seen.insert(key.clone()) {
                policies.push(key);
            }
        }
    }
    policies
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 权限码解析() {
        assert_eq!(parse_perm_code("sys:user:create"), Some(("sys", "user", "create")));
        assert_eq!(parse_perm_code("sys:user"), None);
        assert_eq!(parse_perm_code("::create"), None);
    }
}
