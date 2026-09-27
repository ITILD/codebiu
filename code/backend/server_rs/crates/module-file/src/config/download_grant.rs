//! 业务模块下载授权注册表(对齐 Python module_file/config/download_grant.py)
//!
//! 文件管理的下载权限(main:file:download)独立于浏览(read), 默认仅 admin 角色持有;
//! 业务条目(rag 等以 source_module 标记的条目)可由来源模块注册授权钩子补充放行口径。
//!
//! 接入约定(与 ensure_module_root 同源):
//!   业务模块在启动/导入期调用 register_download_grant(module_key, fn) 注册异步判定函数;
//!   fn(user_id, entry) -> bool, 返回 true 表示放行下载。
//!   module_file 不反向依赖业务模块(避免循环依赖), 注册方向始终为 业务 -> 文件。

use std::collections::HashMap;
use std::future::Future;
use std::sync::{Arc, OnceLock, RwLock};

use crate::do_::entity::file_entry;
use futures::future::BoxFuture;

/// 授权钩子类型: (user_id, entry) -> 是否放行(异步, 所有权转移以便跨 await)
pub type DownloadGrantFn =
    Arc<dyn Fn(String, file_entry::Model) -> BoxFuture<'static, bool> + Send + Sync>;

/// 全局注册表(进程级单例, 后注册覆盖先注册)
fn registry() -> &'static RwLock<HashMap<String, DownloadGrantFn>> {
    static REG: OnceLock<RwLock<HashMap<String, DownloadGrantFn>>> = OnceLock::new();
    REG.get_or_init(|| RwLock::new(HashMap::new()))
}

/// 注册业务模块的下载授权判定钩子(幂等, 后注册覆盖先注册)
pub fn register_download_grant<F, Fut>(module_key: &str, f: F)
where
    F: Fn(String, file_entry::Model) -> Fut + Send + Sync + 'static,
    Fut: Future<Output = bool> + Send + 'static,
{
    let wrapped: DownloadGrantFn = Arc::new(move |uid, entry| {
        Box::pin(f(uid, entry)) as BoxFuture<'static, bool>
    });
    registry()
        .write()
        .expect("下载授权注册表锁")
        .insert(module_key.to_string(), wrapped);
}

/// 获取业务模块的下载授权钩子(未注册返回 None)
pub fn get_download_grant(module_key: &str) -> Option<DownloadGrantFn> {
    registry()
        .read()
        .expect("下载授权注册表锁")
        .get(module_key)
        .cloned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn 注册与查询下载授权钩子() {
        register_download_grant("test_mod", |uid, entry| async move {
            uid == "u1" && entry.name == "a.txt"
        });
        let grant = get_download_grant("test_mod").expect("钩子应已注册");
        let entry = file_entry::Model {
            id: "e".into(),
            pid: None,
            name: "a.txt".into(),
            logical_path: "/a.txt".into(),
            is_directory: false,
            content_hash: None,
            file_size_bytes: None,
            file_extension: None,
            mime_type: None,
            description: None,
            tags: None,
            is_active: true,
            source_module: None,
            group_id: None,
            user_id: None,
            entry_status: None,
            created_at: None,
            updated_at: chrono::Utc::now().into(),
        };

        assert!(grant("u1".into(), entry.clone()).await);
        assert!(!grant("u2".into(), entry).await);
        assert!(get_download_grant("not_registered").is_none());
    }
}
