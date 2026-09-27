//! 文件服务(对齐 Python module_file/service/filesystem.py)
//!
//! 提供虚拟文件系统的上传/下载/目录管理/搜索/复制/统计/迁移等能力。
//! `guard=true` 时启用业务条目只读拦截(HTTP 文件管理口径), 业务模块注入的
//! 实例(guard=false)可自由管理自己的条目。

use std::collections::HashMap;
use std::sync::Arc;

use base64::engine::general_purpose::URL_SAFE_NO_PAD;
use base64::Engine;
use bytes::Bytes;
use crate::do_::entity::file_entry;
use crate::do_::entity::sea_orm_active_enums::{Storagetype, Taskstatus};
use futures::future::BoxFuture;
use futures::stream::BoxStream;
use hmac::{Hmac, Mac};
use sea_orm::DatabaseConnection;
use sha2::{Digest, Sha256};

use common::config::dynamic::TokenSettings;
use common::runtime::AppState;
use common::utils::error::AppError;
use common::utils::pagination::{PaginationParams, PaginationResponse};

use crate::config::download_grant;
use crate::dao::{file_content_dao, file_entry_dao};
use crate::do_::filesystem::{
    storage_type_enum_str, today_key, FileContentCreate, FileContentPatch, FileEntryCreate,
    FileEntryDetailResp, FileEntryPatch, FileEntryResp, EntryCreateRequest, MultipartCompleteRequest,
    MultipartInitRequest, MultipartInitResponse, MultipartPartInfo, MigrateRequest, MigrateResult,
    StorageStats, UploadModeResponse,
};
use crate::do_::storage::{StorageConfig, StorageType};
use crate::utils::mime;
use crate::utils::storage::local::hex_encode;
use crate::utils::storage::{self, PartInfo, Storage};

/// 单片大小 8MB
pub const MULTIPART_PART_SIZE: i64 = 8 * 1024 * 1024;
/// 分片会话凭证有效期 24h
const MULTIPART_TOKEN_TTL: i64 = 24 * 3600;
/// 预签名URL有效期 1h
pub const PRESIGN_EXPIRES: u64 = 3600;

/// 内容级上传结果元数据(对齐 Python upload_content_bytes/complete_multipart_session 返回 dict)
#[derive(Debug, Clone)]
pub struct ContentMeta {
    pub content_hash: String,
    pub physical_storage: String,
    pub file_size_bytes: i64,
    pub mime_type: Option<String>,
}

/// 分片会话凭证载荷(自包含物理键/存储会话ID/哈希/模式)
#[derive(Debug, Clone)]
struct MultipartToken {
    key: String,
    uid: String,
    hash: String,
    mode: String,
}

/// 文件服务(guard=true 时业务条目只读)
#[derive(Clone)]
pub struct FileService {
    state: AppState,
    guard: bool,
}

impl FileService {
    /// 构建服务实例
    ///
    /// :param guard: 业务条目只读拦截开关(仅文件管理 HTTP 层开启)
    pub fn new(state: AppState, guard: bool) -> Self {
        Self { state, guard }
    }

    /// 数据库连接
    fn db(&self) -> &DatabaseConnection {
        &self.state.db
    }

    /// 全局存储单例(local/s3 按动态配置惰性装配)
    pub async fn storage(&self) -> Result<Arc<dyn Storage>, AppError> {
        storage::get(&self.state).await
    }

    /// 存储配置单例(限额/类型)
    pub async fn storage_config(&self) -> Result<StorageConfig, AppError> {
        storage::config(&self.state).await
    }

    /// 按扩展名推断MIME类型(与 Python mimetypes.guess_type 对齐, 未知返回 None)
    pub(crate) fn guess_mime(&self, filename: &str) -> Option<String> {
        mime::guess(filename)
    }

    /// 业务条目只读拦截: source_module 标记的业务条目(rag/avatar等)禁止在文件管理中变更
    fn ensure_module_writable(&self, entry: &file_entry::Model) -> Result<(), AppError> {
        if !self.guard {
            return Ok(());
        }
        if let Some(m) = &entry.source_module {
            if m != "file" {
                return Err(AppError::business("该条目由业务模块管理, 请到对应业务模块操作"));
            }
        }
        Ok(())
    }

    /// 取活跃条目(不存在/已删除 → 404)
    async fn get_active(&self, entry_id: &str) -> Result<file_entry::Model, AppError> {
        let entry = file_entry_dao::get(self.db(), entry_id).await?;
        entry
            .filter(|e| e.is_active)
            .ok_or_else(|| AppError::not_found("条目不存在或已被删除"))
    }

    /// 按ID重新查询条目并转响应
    async fn get_resp(&self, entry_id: &str) -> Result<FileEntryResp, AppError> {
        file_entry_dao::get(self.db(), entry_id)
            .await?
            .map(FileEntryResp::from)
            .ok_or_else(|| AppError::not_found(format!("未找到ID为 {entry_id} 的文件")))
    }

    /// 释放文件内容引用(计数-1, 归零时清理物理文件与内容记录)
    async fn release_content(&self, content_hash: Option<&str>) -> Result<(), AppError> {
        let Some(hash) = content_hash else {
            return Ok(());
        };
        file_content_dao::ref_count_change(self.db(), hash, -1).await?;
        if let Some(fc) = file_content_dao::get_by_content_hash(self.db(), hash).await? {
            if fc.ref_count <= 0 {
                // 引用归零: 清理物理文件与内容记录(失败仅告警, 可由后台任务兜底)
                if let Some(key) = &fc.physical_storage {
                    let s = self.storage().await?;
                    if !s.delete(key).await {
                        tracing::warn!("清理物理文件失败(可由后台任务重试): {key}");
                    }
                }
                file_content_dao::delete(self.db(), hash).await?;
            }
        }
        Ok(())
    }

    // ==================== 删除逻辑 ====================

    /// 删除文件记录(逻辑删除条目, 释放内容引用)
    pub async fn delete_file(&self, entry_id: &str) -> Result<(), AppError> {
        let entry = file_entry_dao::get(self.db(), entry_id).await?;
        let Some(entry) = entry.filter(|e| e.is_active) else {
            return Err(AppError::not_found(format!("未找到ID为 {entry_id} 的文件")));
        };
        self.ensure_module_writable(&entry)?;
        if entry.is_directory {
            return Err(AppError::business("目录请使用目录删除接口"));
        }
        file_entry_dao::soft_delete(self.db(), entry_id).await?;
        self.release_content(entry.content_hash.as_deref()).await
    }

    /// 递归删除目录及其全部子项(虚拟文件系统)
    pub async fn delete_folder(&self, folder_id: &str) -> Result<(), AppError> {
        let folder = file_entry_dao::get(self.db(), folder_id).await?;
        if let Some(f) = &folder {
            self.ensure_module_writable(f)?;
        }
        // 递归 CTE 获取子树全部条目ID(含目录自身)
        let subtree_ids = file_entry_dao::get_subtree_ids(self.db(), folder_id).await?;
        if subtree_ids.is_empty() {
            return Err(AppError::not_found(format!("未找到ID为 {folder_id} 的目录")));
        }
        file_entry_dao::batch_soft_delete(self.db(), &subtree_ids).await?;
        // 对子树中的文件统一释放内容引用(哈希已去重)
        let content_hashes = file_entry_dao::get_content_hashes_by_ids(self.db(), &subtree_ids).await?;
        for content_hash in content_hashes {
            self.release_content(Some(&content_hash)).await?;
        }
        Ok(())
    }

    /// 批量删除条目(文件与目录混选, 目录递归删除子树; 单项失败不阻断其余项)
    pub async fn batch_delete(
        &self,
        entry_ids: Vec<String>,
    ) -> Result<crate::do_::filesystem::BatchDeleteResult, AppError> {
        let mut deleted: i64 = 0;
        let mut failed = Vec::new();
        for entry_id in entry_ids {
            let outcome: Result<(), AppError> = async {
                let entry = file_entry_dao::get(self.db(), &entry_id).await?;
                let Some(entry) = entry.filter(|e| e.is_active) else {
                    return Err(AppError::business("条目不存在或已删除"));
                };
                self.ensure_module_writable(&entry)?;
                if entry.is_directory {
                    // 目录: 递归 CTE 取子树, 批量逻辑删除后统一释放内容引用
                    let subtree_ids = file_entry_dao::get_subtree_ids(self.db(), &entry_id).await?;
                    file_entry_dao::batch_soft_delete(self.db(), &subtree_ids).await?;
                    let hashes =
                        file_entry_dao::get_content_hashes_by_ids(self.db(), &subtree_ids).await?;
                    for h in hashes {
                        self.release_content(Some(&h)).await?;
                    }
                } else {
                    file_entry_dao::soft_delete(self.db(), &entry_id).await?;
                    self.release_content(entry.content_hash.as_deref()).await?;
                }
                Ok(())
            }
            .await;
            match outcome {
                Ok(()) => deleted += 1,
                Err(e) => {
                    tracing::warn!("批量删除条目失败 {entry_id}: {e}");
                    failed.push(crate::do_::filesystem::BatchDeleteItemError {
                        id: entry_id,
                        error: e.to_string(),
                    });
                }
            }
        }
        Ok(crate::do_::filesystem::BatchDeleteResult { deleted, failed })
    }

    // ==================== 更新/重命名/移动 ====================

    /// 更新条目信息(名称变更自动委托重命名逻辑, 保证路径一致)
    pub async fn update(
        &self,
        file_id: &str,
        req: crate::do_::filesystem::FileEntryUpdateReq,
    ) -> Result<FileEntryResp, AppError> {
        let entry = self.get_active(file_id).await?;
        self.ensure_module_writable(&entry)?;
        // 名称变更走重命名(维护子树路径一致性); 空名跳过(与 Python `if new_name` 一致)
        if let Some(new_name) = req.name.as_deref() {
            if !new_name.is_empty() && new_name != entry.name {
                self.rename(file_id, new_name).await?;
            }
        }
        // 描述/标签变更直接更新(标签组支持手动输入与后续RAG智能提取写入)
        let mut patch = FileEntryPatch::default();
        if let Some(desc) = &req.description {
            if Some(desc) != entry.description.as_ref() {
                patch.description = Some(Some(desc.clone()));
            }
        }
        if let Some(tags) = &req.tags {
            if tags != &crate::do_::filesystem::json_to_tags(&entry.tags) {
                patch.tags = Some(tags.clone());
            }
        }
        if patch.description.is_some() || patch.tags.is_some() {
            file_entry_dao::update(self.db(), file_id, patch).await?;
        }
        self.get_resp(file_id).await
    }

    /// 重命名条目(目录重命名时同步更新子树逻辑路径)
    pub async fn rename(&self, entry_id: &str, new_name: &str) -> Result<FileEntryResp, AppError> {
        let entry = self.get_active(entry_id).await?;
        self.ensure_module_writable(&entry)?;
        let new_name = new_name.trim();
        if new_name.is_empty() {
            return Err(AppError::business("名称不能为空"));
        }
        if entry.name == new_name {
            return Ok(entry.into());
        }
        // 同目录重名校验(排除自身)
        if file_entry_dao::exists_by_pid_name(self.db(), entry.pid.as_deref(), new_name, Some(entry_id))
            .await?
        {
            return Err(AppError::conflict(format!("当前目录下已存在同名条目: {new_name}")));
        }
        let old_path = entry.logical_path.clone();
        let parent_path = old_path.rsplit_once('/').map(|(p, _)| p).unwrap_or("");
        let new_path = format!("{parent_path}/{new_name}");
        file_entry_dao::update(
            self.db(),
            entry_id,
            FileEntryPatch {
                name: Some(new_name.to_string()),
                logical_path: Some(new_path.clone()),
                ..Default::default()
            },
        )
        .await?;
        // 目录: 子孙逻辑路径前缀同步替换
        if entry.is_directory {
            file_entry_dao::update_children_path_prefix(self.db(), &old_path, &new_path).await?;
        }
        self.get_resp(entry_id).await
    }

    /// 移动条目到目标目录(目录移动时同步更新子树逻辑路径)
    pub async fn move_entry(
        &self,
        entry_id: &str,
        target_pid: Option<String>,
    ) -> Result<FileEntryResp, AppError> {
        let entry = self.get_active(entry_id).await?;
        self.ensure_module_writable(&entry)?;
        // 空串按根目录处理(与 Python `target_pid or None` 一致)
        let target_pid = target_pid.filter(|p| !p.is_empty());
        let new_path;
        if let Some(tpid) = &target_pid {
            let target = file_entry_dao::get(self.db(), tpid).await?;
            let Some(target) = target.filter(|e| e.is_active) else {
                return Err(AppError::not_found("目标目录不存在或已被删除"));
            };
            if !target.is_directory {
                return Err(AppError::business("目标条目不是目录"));
            }
            self.ensure_module_writable(&target)?;
            // 环形引用防护: 目标不能是自身或自身的子孙目录
            if target.logical_path == entry.logical_path
                || target.logical_path.starts_with(&format!("{}/", entry.logical_path))
            {
                return Err(AppError::business("不能移动到自身或其子目录下"));
            }
            new_path = format!("{}/{}", target.logical_path.trim_end_matches('/'), entry.name);
        } else {
            new_path = format!("/{}", entry.name);
        }
        // 位置未变化直接返回
        if new_path == entry.logical_path && target_pid == entry.pid.clone().filter(|p| !p.is_empty())
        {
            return Ok(entry.into());
        }
        // 目标目录同名冲突校验(排除自身)
        if file_entry_dao::exists_by_pid_name(
            self.db(),
            target_pid.as_deref(),
            &entry.name,
            Some(entry_id),
        )
        .await?
        {
            return Err(AppError::conflict(format!(
                "目标目录下已存在同名条目: {}",
                entry.name
            )));
        }
        let old_path = entry.logical_path.clone();
        file_entry_dao::update(
            self.db(),
            entry_id,
            FileEntryPatch {
                // Some(None) = 移回根目录
                pid: Some(target_pid.clone()),
                logical_path: Some(new_path.clone()),
                ..Default::default()
            },
        )
        .await?;
        if entry.is_directory {
            file_entry_dao::update_children_path_prefix(self.db(), &old_path, &new_path).await?;
        }
        self.get_resp(entry_id).await
    }

    // ==================== 查询/详情/浏览 ====================

    /// 获取文件或目录信息
    pub async fn get_file_entry(&self, id: &str) -> Result<Option<file_entry::Model>, AppError> {
        file_entry_dao::get(self.db(), id).await
    }

    /// 获取条目详情(条目+内容元数据+上传用户名)
    pub async fn get_entry_detail(
        &self,
        entry_id: &str,
    ) -> Result<Option<FileEntryDetailResp>, AppError> {
        let Some((entry, content)) = file_entry_dao::get_with_content(self.db(), entry_id).await?
        else {
            return Ok(None);
        };
        // 上传用户名(昵称优先, 空昵称回落用户名)
        let owner_name = match &entry.user_id {
            Some(uid) => {
                module_authorization::dao::user::get(self.db(), uid)
                    .await
                    .map(|u| {
                        u.nickname
                            .filter(|n| !n.is_empty())
                            .unwrap_or(u.username)
                    })
            }
            None => None,
        };
        Ok(Some(FileEntryDetailResp {
            entry: entry.into(),
            physical_storage: content.as_ref().and_then(|c| c.physical_storage.clone()),
            ref_count: content.as_ref().map(|c| c.ref_count as i64),
            storage_type: content
                .as_ref()
                .and_then(|c| c.storage_type.as_ref().map(storage_type_enum_str))
                .map(|s| s.to_string()),
            content_status: content
                .as_ref()
                .and_then(|c| c.content_status.as_ref().map(crate::do_::filesystem::task_status_str))
                .map(|s| s.to_string()),
            owner_name,
        }))
    }

    /// 分页查询指定目录下的条目(目录排前, 名称排序)
    pub async fn list_by_pid(
        &self,
        pid: Option<&str>,
        pagination: &PaginationParams,
        name: Option<&str>,
    ) -> Result<PaginationResponse<FileEntryResp>, AppError> {
        let items = file_entry_dao::list_by_pid(self.db(), pid, pagination, name).await?;
        let total = file_entry_dao::count_by_pid(self.db(), pid, name).await? as i64;
        Ok(PaginationResponse::create(
            items.into_iter().map(FileEntryResp::from).collect(),
            total,
            pagination,
        ))
    }

    /// 查询指定目录下的全部子目录(目录树选择用)
    pub async fn list_dirs(
        &self,
        pid: Option<&str>,
    ) -> Result<Vec<FileEntryResp>, AppError> {
        Ok(file_entry_dao::list_dirs_by_pid(self.db(), pid)
            .await?
            .into_iter()
            .map(FileEntryResp::from)
            .collect())
    }

    // ==================== 目录创建(业务模块共用) ====================

    /// 创建目录(虚拟文件系统)
    ///
    /// :param source_module: 来源模块key(顶层模块根专用; pid 有值时自动从父目录继承)
    pub async fn create_folder(
        &self,
        name: String,
        pid: Option<&str>,
        owner_user_id: Option<&str>,
        source_module: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let mut source_module = source_module.map(|s| s.to_string());
        let logical_path = if let Some(p) = pid {
            let parent = file_entry_dao::get(self.db(), p).await?;
            let Some(parent) = parent.filter(|e| e.is_active) else {
                return Err(AppError::not_found("父目录不存在或已被删除"));
            };
            if !parent.is_directory {
                return Err(AppError::business("父级条目不是目录"));
            }
            self.ensure_module_writable(&parent)?;
            // 来源标记继承: 业务模块子目录自动携带父目录的模块标记
            source_module = source_module.or_else(|| parent.source_module.clone());
            format!("{}/{}", parent.logical_path.trim_end_matches('/'), name)
        } else {
            format!("/{name}")
        };
        // 同目录下名称唯一校验
        if file_entry_dao::exists_by_pid_name(self.db(), pid, &name, None).await? {
            return Err(AppError::conflict(format!("当前目录下已存在同名条目: {name}")));
        }
        let folder_id = file_entry_dao::add(
            self.db(),
            FileEntryCreate {
                name,
                pid: pid.map(|p| p.to_string()),
                logical_path,
                is_directory: true,
                source_module,
                user_id: owner_user_id.map(|s| s.to_string()),
                ..Default::default()
            },
        )
        .await?;
        self.get_resp(&folder_id).await
    }

    /// 幂等创建目录: 已存在同名目录直接返回(业务模块根/项目文件夹补建用)
    pub async fn ensure_folder(
        &self,
        name: &str,
        pid: Option<&str>,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let existing = file_entry_dao::get_by_pid_name(self.db(), pid, name).await?;
        if let Some(e) = existing.filter(|e| e.is_directory) {
            return Ok(e.into());
        }
        // 同名为文件或不存在 → 交给 create_folder(内部有冲突与父目录校验)
        self.create_folder(name.to_string(), pid, owner_user_id, None)
            .await
    }

    /// 获取或创建业务模块的顶层根目录(幂等, 按 source_module 匹配)
    pub async fn ensure_module_root(
        &self,
        module_key: &str,
        label: &str,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        if let Some(root) = file_entry_dao::get_module_root(self.db(), module_key).await? {
            return Ok(root.into());
        }
        self.create_folder(label.to_string(), None, owner_user_id, Some(module_key))
            .await
    }

    // ==================== 通用上传/下载(直传小文件) ====================

    /// 校验父目录有效性, 返回逻辑路径与父条目(上传/秒传/分片共用)
    async fn get_parent_dir(
        &self,
        pid: Option<&str>,
    ) -> Result<(String, Option<file_entry::Model>), AppError> {
        let Some(pid) = pid.filter(|p| !p.is_empty()) else {
            return Ok((String::new(), None));
        };
        let parent = file_entry_dao::get(self.db(), pid).await?;
        let Some(parent) = parent.filter(|e| e.is_active) else {
            return Err(AppError::not_found("父目录不存在或已被删除"));
        };
        // 与 create_folder 一致: 文件管理口径禁止向业务条目目录内上传
        self.ensure_module_writable(&parent)?;
        if !parent.is_directory {
            return Err(AppError::business("父级条目不是目录"));
        }
        Ok((parent.logical_path.trim_end_matches('/').to_string(), Some(parent)))
    }

    /// 基于已完成的内容记录创建虚拟文件条目(直传/分片/秒传共用收尾逻辑)
    #[allow(clippy::too_many_arguments)]
    async fn create_entry_from_content(
        &self,
        name: &str,
        pid: Option<&str>,
        dir_path: &str,
        content_hash: &str,
        file_size_bytes: i64,
        mime_type: Option<&str>,
        description: Option<&str>,
        owner_user_id: Option<&str>,
        source_module: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        // Python: file_ext = Path(name).suffix → ".pdf"; file_extension = 去点后缀(无后缀为空串)
        let ext = std::path::Path::new(name)
            .extension()
            .map(|e| e.to_string_lossy().to_string())
            .unwrap_or_default();
        let logical_path = format!("{dir_path}/{name}");
        let created_id = file_entry_dao::add(
            self.db(),
            FileEntryCreate {
                name: name.to_string(),
                pid: pid.filter(|p| !p.is_empty()).map(|p| p.to_string()),
                logical_path: logical_path.clone(),
                is_directory: false,
                content_hash: Some(content_hash.to_string()),
                file_size_bytes: Some(file_size_bytes),
                file_extension: Some(ext),
                mime_type: Some(mime_type.unwrap_or("application/octet-stream").to_string()),
                description: description.map(|d| d.to_string()),
                tags: Vec::new(),
                source_module: source_module.map(|s| s.to_string()),
                user_id: owner_user_id.map(|s| s.to_string()),
            },
        )
        .await?;
        // 引用计数+1(同时将内容状态置为SUCCESS)
        file_content_dao::ref_count_change(self.db(), content_hash, 1).await?;
        tracing::info!("文件上传成功: {name} -> {logical_path}");
        self.get_resp(&created_id).await
    }

    /// 上传文件到指定目录(小文件直传入口, 超过 max_size 请走分片上传)
    pub async fn upload_file(
        &self,
        filename: &str,
        content: Bytes,
        description: Option<&str>,
        pid: Option<&str>,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        // 校验父目录(同时拿到父条目以继承来源模块标记)
        let (dir_path, parent) = self.get_parent_dir(pid).await?;
        let cfg = self.storage_config().await?;
        // 大小与MIME类型校验(直传仅服务小文件)
        if content.len() > cfg.limits().max_size_bytes() {
            return Err(AppError::business(format!(
                "文件大小超过直传限制: {}MB, 请使用分片上传",
                cfg.limits().max_size
            )));
        }
        let mime_type = self
            .guess_mime(filename)
            .unwrap_or_else(|| "application/octet-stream".to_string());
        if !cfg.limits().is_mime_allowed(Some(&mime_type)) {
            return Err(AppError::business(format!("不支持的文件类型: {mime_type}")));
        }
        // 同目录同名冲突校验
        if file_entry_dao::exists_by_pid_name(self.db(), pid, filename, None).await? {
            return Err(AppError::conflict(format!("当前目录下已存在同名文件: {filename}")));
        }
        // 内容哈希去重: 已存在且完成的内容直接复用(秒传)
        let meta = self.upload_content_bytes(&content, filename).await?;
        self.create_entry_from_content(
            filename,
            pid,
            &dir_path,
            &meta.content_hash,
            content.len() as i64,
            Some(&mime_type),
            description,
            owner_user_id,
            parent.as_ref().and_then(|p| p.source_module.clone()).as_deref(),
        )
        .await
    }

    /// 字节级内容存储(内容级口径): 大小校验+SHA-256去重+内容记录置SUCCESS
    pub async fn upload_content_bytes(
        &self,
        content: &[u8],
        filename: &str,
    ) -> Result<ContentMeta, AppError> {
        let cfg = self.storage_config().await?;
        if content.len() > cfg.limits().max_size_bytes() {
            return Err(AppError::business(format!(
                "文件大小超过直传限制: {}MB, 请使用分片上传",
                cfg.limits().max_size
            )));
        }
        let mime_type = self.guess_mime(filename);
        let content_hash = hex_encode(&Sha256::digest(content));
        let file_ext = std::path::Path::new(filename)
            .extension()
            .map(|e| format!(".{}", e.to_string_lossy()))
            .unwrap_or_default();
        let existing = file_content_dao::get_by_content_hash(self.db(), &content_hash).await?;
        let physical_storage =
            if existing.as_ref().is_some_and(|fc| fc.content_status == Some(Taskstatus::Success)) {
                // 已完成内容直接复用物理键(秒传)
                existing
                    .as_ref()
                    .and_then(|fc| fc.physical_storage.clone())
                    .unwrap_or_default()
            } else {
                // 新内容或上次上传中断: 覆盖写入物理存储(哈希命名, 日期分目录)
                let ps = format!("uploads/{}/{}{file_ext}", today_key(), content_hash);
                self.storage().await?.save(&ps, content).await?;
                if existing.is_none() {
                    file_content_dao::add(
                        self.db(),
                        FileContentCreate {
                            content_hash: content_hash.clone(),
                            physical_storage: ps.clone(),
                            file_size_bytes: content.len() as i64,
                            storage_type: db_storage_enum(cfg.storage_type()),
                        },
                    )
                    .await?;
                } else if existing.as_ref().and_then(|fc| fc.physical_storage.as_deref()) != Some(ps.as_str()) {
                    // 中断记录的旧物理键与新键不一致时校正(避免引用悬空)
                    file_content_dao::update(
                        self.db(),
                        &content_hash,
                        FileContentPatch {
                            physical_storage: Some(ps.clone()),
                            file_size_bytes: Some(content.len() as i64),
                            ..Default::default()
                        },
                    )
                    .await?;
                }
                ps
            };
        Ok(ContentMeta {
            content_hash,
            physical_storage,
            file_size_bytes: content.len() as i64,
            mime_type,
        })
    }

    // ==================== 分片上传(multipart, 大文件) ====================
    // 会话凭证 token: base64url(json) + HMAC-SHA256 签名, 无状态可跨请求传递

    /// 对分片会话凭证载荷计算HMAC-SHA256签名(密钥取当前动态令牌配置)
    async fn multipart_sign(&self, payload: &str) -> Result<String, AppError> {
        let ts: TokenSettings = self.state.settings.get("token").await?;
        let mut mac = <Hmac<Sha256> as Mac>::new_from_slice(ts.secret_key.as_bytes())
            .map_err(|e| AppError::internal(format!("HMAC 密钥错误: {e}")))?;
        mac.update(payload.as_bytes());
        Ok(hex_encode(&mac.finalize().into_bytes()))
    }

    /// 生成分片上传会话凭证(签名token, 防伪造/防路径穿越)
    async fn make_multipart_token(
        &self,
        key: &str,
        upload_id: &str,
        content_hash: &str,
        mode: &str,
    ) -> Result<String, AppError> {
        let exp = chrono::Utc::now().timestamp() + MULTIPART_TOKEN_TTL;
        let json = serde_json::json!({
            "key": key, "uid": upload_id, "hash": content_hash, "mode": mode, "exp": exp,
        });
        let payload = URL_SAFE_NO_PAD.encode(serde_json::to_vec(&json)?);
        let sig = self.multipart_sign(&payload).await?;
        Ok(format!("{payload}.{sig}"))
    }

    /// 解析并校验分片上传会话凭证
    async fn parse_multipart_token(&self, token: &str) -> Result<MultipartToken, AppError> {
        let Some((payload, sig)) = token.rsplit_once('.') else {
            return Err(AppError::business("非法的分片上传凭证"));
        };
        // 恒定时间比较(与 Python hmac.compare_digest 一致)
        let expect = self.multipart_sign(payload).await?;
        if !subtle_equal(sig, &expect) {
            return Err(AppError::business("非法的分片上传凭证"));
        }
        let bytes = URL_SAFE_NO_PAD
            .decode(payload)
            .map_err(|_| AppError::business("非法的分片上传凭证"))?;
        let v: serde_json::Value = serde_json::from_slice(&bytes)
            .map_err(|_| AppError::business("非法的分片上传凭证"))?;
        let exp = v.get("exp").and_then(|x| x.as_i64()).unwrap_or(0);
        if chrono::Utc::now().timestamp() > exp {
            return Err(AppError::business("分片上传会话已过期,请重新上传"));
        }
        Ok(MultipartToken {
            key: v.get("key").and_then(|x| x.as_str()).unwrap_or_default().to_string(),
            uid: v.get("uid").and_then(|x| x.as_str()).unwrap_or_default().to_string(),
            hash: v.get("hash").and_then(|x| x.as_str()).unwrap_or_default().to_string(),
            mode: v.get("mode").and_then(|x| x.as_str()).unwrap_or_default().to_string(),
        })
    }

    /// 初始化上传(秒传/去重/校验都在凭证签发阶段完成)
    pub async fn init_multipart_upload(
        &self,
        req: &MultipartInitRequest,
    ) -> Result<MultipartInitResponse, AppError> {
        // ===== 校验阶段(拿凭证时完成) =====
        let (dir_path, _parent) = self.get_parent_dir(req.pid.as_deref()).await?;
        if file_entry_dao::exists_by_pid_name(self.db(), req.pid.as_deref(), &req.filename, None)
            .await?
        {
            return Err(AppError::conflict(format!(
                "当前目录下已存在同名文件: {}",
                req.filename
            )));
        }
        let cfg = self.storage_config().await?;
        let mime_type = self
            .guess_mime(&req.filename)
            .or_else(|| req.content_type.clone())
            .unwrap_or_else(|| "application/octet-stream".to_string());
        if !cfg.limits().is_mime_allowed(Some(&mime_type)) {
            return Err(AppError::business(format!("不支持的文件类型: {mime_type}")));
        }
        tracing::info!(
            "中转初始化: {} ({}B) dir={}",
            req.filename,
            req.file_size_bytes,
            if dir_path.is_empty() { "/" } else { &dir_path }
        );
        // ===== 内容级复用逻辑: 秒传判断/内容记录/凭证签发 =====
        self.init_multipart_session(req).await
    }

    /// 内容级分片上传初始化(无目录/同名校验): 秒传判断+内容记录+凭证签发
    pub async fn init_multipart_session(
        &self,
        req: &MultipartInitRequest,
    ) -> Result<MultipartInitResponse, AppError> {
        // 秒传判断: 相同内容已完成上传
        let existing = file_content_dao::get_by_content_hash(self.db(), &req.content_hash).await?;
        if existing.as_ref().is_some_and(|fc| fc.content_status == Some(Taskstatus::Success)) {
            return Ok(MultipartInitResponse {
                is_existing: true,
                upload_id: None,
                part_size: MULTIPART_PART_SIZE,
                mode: "proxy".to_string(),
                part_urls: None,
            });
        }
        // 内容记录: 直接以前端SHA-256建PENDING记录(完成时按存储侧归位结果校正)
        let cfg = self.storage_config().await?;
        let physical_key = if let Some(fc) = &existing {
            fc.physical_storage.clone().unwrap_or_default()
        } else {
            let ext = std::path::Path::new(&req.filename)
                .extension()
                .map(|e| format!(".{}", e.to_string_lossy()))
                .unwrap_or_default();
            let ps = format!(
                "uploads/{}/{}{ext}",
                today_key(),
                uuid::Uuid::new_v4().simple()
            );
            file_content_dao::add(
                self.db(),
                FileContentCreate {
                    content_hash: req.content_hash.clone(),
                    physical_storage: ps.clone(),
                    file_size_bytes: req.file_size_bytes,
                    storage_type: db_storage_enum(cfg.storage_type()),
                },
            )
            .await?;
            ps
        };
        // 凭证签发: 按存储能力决定 direct(预签名直传) / proxy(服务端中转)
        let content_type = self
            .guess_mime(&req.filename)
            .or_else(|| req.content_type.clone())
            .unwrap_or_else(|| "application/octet-stream".to_string());
        let s = self.storage().await?;
        let storage_upload_id = s.create_multipart(&physical_key, &content_type).await?;
        if s.supports_presign() {
            // 逐片生成预签名URL, 全部成功才走直传, 否则降级中转(不阻断上传)
            match self
                .try_presign_parts(s.as_ref(), &physical_key, &storage_upload_id, req.file_size_bytes)
                .await
            {
                Ok(Some(part_urls)) => {
                    let token = self
                        .make_multipart_token(&physical_key, &storage_upload_id, &req.content_hash, "direct")
                        .await?;
                    tracing::info!(
                        "直传初始化(内容级): {} ({}B, {}片)",
                        req.filename,
                        req.file_size_bytes,
                        part_urls.len()
                    );
                    return Ok(MultipartInitResponse {
                        is_existing: false,
                        upload_id: Some(token),
                        part_size: MULTIPART_PART_SIZE,
                        mode: "direct".to_string(),
                        part_urls: Some(part_urls),
                    });
                }
                Ok(None) => {}
                Err(e) => tracing::warn!("预签名生成失败,降级为中转模式: {e}"),
            }
        }
        let token = self
            .make_multipart_token(&physical_key, &storage_upload_id, &req.content_hash, "proxy")
            .await?;
        tracing::info!("中转初始化(内容级): {} ({}B)", req.filename, req.file_size_bytes);
        Ok(MultipartInitResponse {
            is_existing: false,
            upload_id: Some(token),
            part_size: MULTIPART_PART_SIZE,
            mode: "proxy".to_string(),
            part_urls: None,
        })
    }

    /// 为每个分片生成预签名URL(任一片失败返回降级信号)
    async fn try_presign_parts(
        &self,
        s: &dyn Storage,
        key: &str,
        uid: &str,
        file_size_bytes: i64,
    ) -> Result<Option<Vec<String>>, AppError> {
        let part_count = (file_size_bytes + MULTIPART_PART_SIZE - 1) / MULTIPART_PART_SIZE;
        let mut urls = Vec::with_capacity(part_count.max(0) as usize);
        for n in 1..=part_count {
            match s.presign_put(key, Some(uid), Some(n), PRESIGN_EXPIRES).await {
                Ok(Some(u)) => urls.push(u),
                Ok(None) => return Ok(None),
                Err(e) => return Err(e),
            }
        }
        Ok(Some(urls))
    }

    /// 上传单个分片(凭证即会话, 免查库)
    pub async fn upload_multipart_part(
        &self,
        upload_id: &str,
        part_number: i64,
        content: Bytes,
    ) -> Result<MultipartPartInfo, AppError> {
        if !(1..=10000).contains(&part_number) {
            return Err(AppError::business("分片号必须在 1~10000 范围内"));
        }
        if content.len() > MULTIPART_PART_SIZE as usize {
            return Err(AppError::business(format!(
                "单片大小不能超过 {}MB",
                MULTIPART_PART_SIZE / 1024 / 1024
            )));
        }
        let data = self.parse_multipart_token(upload_id).await?;
        let s = self.storage().await?;
        let info = s.upload_part(&data.key, &data.uid, part_number, &content).await?;
        Ok(MultipartPartInfo {
            part_number: info.part_number,
            etag: info.etag,
            size: info.size,
        })
    }

    /// 查询会话中已上传的分片(断点续传)
    pub async fn list_multipart_parts(
        &self,
        upload_id: &str,
    ) -> Result<Vec<MultipartPartInfo>, AppError> {
        let data = self.parse_multipart_token(upload_id).await?;
        let s = self.storage().await?;
        Ok(s.list_parts(&data.key, &data.uid)
            .await?
            .into_iter()
            .map(|p| MultipartPartInfo { part_number: p.part_number, etag: p.etag, size: p.size })
            .collect())
    }

    /// 分片对账(直传完成前校验): 存储侧实际分片 vs 前端提交清单
    async fn reconcile_parts(
        &self,
        data: &MultipartToken,
        req_parts: Vec<MultipartPartInfo>,
    ) -> Result<Vec<PartInfo>, AppError> {
        let s = self.storage().await?;
        let actual = s.list_parts(&data.key, &data.uid).await?;
        let actual_map: HashMap<i64, PartInfo> =
            actual.into_iter().map(|p| (p.part_number, p)).collect();
        let mut sorted = req_parts;
        sorted.sort_by_key(|p| p.part_number);
        let mut out = Vec::with_capacity(sorted.len());
        for (i, p) in sorted.iter().enumerate() {
            if p.part_number != i as i64 + 1 {
                return Err(AppError::business(format!("分片不连续: 缺少第 {} 片", i + 1)));
            }
            let Some(ap) = actual_map.get(&p.part_number) else {
                return Err(AppError::business(format!(
                    "分片 {} 未在存储中找到,请重新上传该分片",
                    p.part_number
                )));
            };
            if p.size != 0 && p.size != ap.size {
                return Err(AppError::business(format!(
                    "分片 {} 大小不一致(声明{}B/实际{}B)",
                    p.part_number, p.size, ap.size
                )));
            }
            let p_etag = p.etag.trim_matches('"');
            if !p.etag.is_empty() && !ap.etag.is_empty() && p_etag != ap.etag.trim_matches('"') {
                return Err(AppError::business(format!(
                    "分片 {} 校验值(ETag)不一致",
                    p.part_number
                )));
            }
            // 以前端分片顺序为准, ETag 缺失时用存储侧记录补齐(S3 complete 必需)
            out.push(PartInfo {
                part_number: p.part_number,
                etag: if p.etag.is_empty() { ap.etag.trim_matches('"').to_string() } else { p_etag.to_string() },
                size: if p.size != 0 { p.size } else { ap.size },
            });
        }
        Ok(out)
    }

    /// 完成上传: 分片对账 -> 存储侧合并归位 -> 建条目(数据面不经过服务端)
    pub async fn complete_multipart_upload(
        &self,
        upload_id: &str,
        req: MultipartCompleteRequest,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let data = self.parse_multipart_token(upload_id).await?;
        let (dir_path, parent) = self.get_parent_dir(req.pid.as_deref()).await?;
        if file_entry_dao::exists_by_pid_name(self.db(), req.pid.as_deref(), &req.filename, None)
            .await?
        {
            return Err(AppError::conflict(format!(
                "当前目录下已存在同名文件: {}",
                req.filename
            )));
        }
        // ===== 内容级复用逻辑: 分片对账/合并归位/哈希校正 =====
        let meta = self
            .complete_multipart_session(upload_id, req.parts.clone(), req.file_size_bytes)
            .await?;
        let mime_type = self
            .guess_mime(&req.filename)
            .unwrap_or_else(|| "application/octet-stream".to_string());
        let entry = self
            .create_entry_from_content(
                &req.filename,
                req.pid.as_deref(),
                &dir_path,
                &meta.content_hash,
                meta.file_size_bytes,
                Some(&mime_type),
                req.description.as_deref(),
                owner_user_id,
                parent.as_ref().and_then(|p| p.source_module.clone()).as_deref(),
            )
            .await?;
        tracing::info!(
            "上传完成({}): {} -> {} ({}B)",
            data.mode,
            req.filename,
            entry.logical_path,
            meta.file_size_bytes
        );
        Ok(entry)
    }

    /// 内容级分片完成: 分片对账 -> 存储侧合并归位 -> 内容记录哈希校正
    pub async fn complete_multipart_session(
        &self,
        upload_id: &str,
        parts: Vec<MultipartPartInfo>,
        file_size_bytes: Option<i64>,
    ) -> Result<ContentMeta, AppError> {
        let data = self.parse_multipart_token(upload_id).await?;
        let s = self.storage().await?;
        let (real_hash, size, final_key): (String, i64, String) = if data.mode == "direct" {
            // 直传: 先与存储侧对账(防伪造清单), 归位信任前端SHA-256(签发阶段已校验)
            let parts = self.reconcile_parts(&data, parts).await?;
            s.complete_multipart(&data.key, &data.uid, &parts, Some(&data.hash))
                .await?
        } else {
            // 中转: 分片完整性预校验(连续性/单片大小), 存储侧合并时算真实SHA-256
            let mut sorted = parts;
            sorted.sort_by_key(|p| p.part_number);
            for (i, p) in sorted.iter().enumerate() {
                if p.part_number != i as i64 + 1 {
                    return Err(AppError::business(format!("分片不连续: 缺少第 {} 片", i + 1)));
                }
                if i < sorted.len() - 1 && p.size != 0 && p.size != MULTIPART_PART_SIZE {
                    return Err(AppError::business(format!("分片 {} 大小不合法", p.part_number)));
                }
            }
            let parts = sorted
                .into_iter()
                .map(|p| PartInfo { part_number: p.part_number, etag: p.etag, size: p.size })
                .collect::<Vec<_>>();
            s.complete_multipart(&data.key, &data.uid, &parts, None).await?
        };
        if let Some(declared) = file_size_bytes {
            if declared != size {
                return Err(AppError::business(format!(
                    "合并后大小({size}B)与声明大小({declared}B)不一致"
                )));
            }
        }
        // 内容记录归位: 前端SHA-256与存储侧实际哈希不一致时(仅中转可能出现)校正记录
        let claimed_hash = data.hash.clone();
        if claimed_hash != real_hash {
            let dup = file_content_dao::get_by_content_hash(self.db(), &real_hash).await?;
            if dup.is_some() {
                file_content_dao::delete(self.db(), &claimed_hash).await?;
            } else {
                file_content_dao::replace_content_hash(self.db(), &claimed_hash, &real_hash, &final_key)
                    .await?;
            }
        } else {
            file_content_dao::update(
                self.db(),
                &claimed_hash,
                FileContentPatch {
                    physical_storage: Some(final_key.clone()),
                    file_size_bytes: Some(size),
                    ..Default::default()
                },
            )
            .await?;
        }
        Ok(ContentMeta {
            content_hash: real_hash,
            physical_storage: final_key,
            file_size_bytes: size,
            mime_type: None,
        })
    }

    /// 取消分片上传会话(清理存储侧已上传分片, 内容记录保留待后续复用)
    pub async fn abort_multipart_upload(&self, upload_id: &str) -> Result<(), AppError> {
        let data = self.parse_multipart_token(upload_id).await?;
        self.storage().await?.abort_multipart(&data.key, &data.uid).await?;
        tracing::info!("分片上传已取消: {}", data.key);
        Ok(())
    }

    /// 基于已完成的内容记录创建文件条目(秒传场景: init 返回 is_existing 后调用)
    pub async fn create_entry(
        &self,
        req: EntryCreateRequest,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let content = file_content_dao::get_by_content_hash(self.db(), &req.content_hash).await?;
        if content.as_ref().is_none_or(|c| c.content_status != Some(Taskstatus::Success)) {
            return Err(AppError::not_found("文件内容不存在或未完成上传,无法创建条目"));
        }
        let (dir_path, parent) = self.get_parent_dir(req.pid.as_deref()).await?;
        if file_entry_dao::exists_by_pid_name(self.db(), req.pid.as_deref(), &req.name, None).await? {
            return Err(AppError::conflict(format!("当前目录下已存在同名文件: {}", req.name)));
        }
        self.create_entry_from_content(
            &req.name,
            req.pid.as_deref(),
            &dir_path,
            &req.content_hash,
            req.file_size_bytes,
            req.mime_type.as_deref(),
            req.description.as_deref(),
            owner_user_id,
            parent.as_ref().and_then(|p| p.source_module.clone()).as_deref(),
        )
        .await
    }

    /// 查询上传模式(前端上传前获取一次, 决定直传/中转策略)
    pub async fn get_upload_mode(&self) -> Result<UploadModeResponse, AppError> {
        let s = self.storage().await?;
        let cfg = self.storage_config().await?;
        Ok(UploadModeResponse {
            mode: if s.supports_presign() { "direct" } else { "proxy" }.to_string(),
            part_size: MULTIPART_PART_SIZE,
            max_size: cfg.limits().max_size as i64,
        })
    }

    // ==================== 下载 ====================

    /// 生成下载直链(直传存储返回预签名URL; local 不支持返回 None 走流式代理)
    pub async fn presign_download_url(&self, file_key: &str, filename: &str) -> Option<String> {
        let s = self.storage().await.ok()?;
        if !s.supports_presign() {
            return None;
        }
        match s.presign_get(file_key, PRESIGN_EXPIRES, Some(filename)).await {
            Ok(url) => url,
            Err(e) => {
                tracing::warn!("下载直链生成失败,降级为流式代理: {e}");
                None
            }
        }
    }

    /// 获取文件下载所需的信息
    ///
    /// :return: (文件名, MIME类型, 物理存储键)
    pub async fn get_file_info_for_download(
        &self,
        entry_id: &str,
    ) -> Result<(String, Option<String>, String), AppError> {
        // 联查条目与内容元数据(物理存储键位于内容表)
        let info = file_entry_dao::get_with_content(self.db(), entry_id).await?;
        let Some((entry, content)) = info else {
            tracing::warn!("文件不存在或已被禁用: {entry_id}");
            return Err(AppError::not_found("文件不存在或已被禁用"));
        };
        if !entry.is_active {
            return Err(AppError::not_found("文件不存在或已被禁用"));
        }
        if entry.is_directory {
            return Err(AppError::business("目录不支持下载"));
        }
        let file_key = content
            .and_then(|c| c.physical_storage)
            .ok_or_else(|| AppError::not_found("文件内容记录缺失"))?;
        // 使用存储接口检查物理文件是否存在
        if !self.storage().await?.exists(&file_key).await {
            tracing::error!("物理文件不存在: {file_key}");
            return Err(AppError::not_found("物理文件不存在"));
        }
        Ok((entry.name, entry.mime_type, file_key))
    }

    /// 流式读取文件内容(分块加载, 避免大文件全量载入内存)
    pub async fn stream_file_content(
        &self,
        file_key: &str,
        chunk_size: usize,
    ) -> Result<BoxStream<'static, Result<Bytes, std::io::Error>>, AppError> {
        self.storage().await?.stream(file_key, chunk_size).await
    }

    // ==================== 路径操作/搜索/复制/读取 ====================

    /// 按逻辑路径精确查询条目
    pub async fn get_by_path(&self, logical_path: &str) -> Result<Option<FileEntryResp>, AppError> {
        Ok(file_entry_dao::get_by_logical_path(self.db(), logical_path)
            .await?
            .map(FileEntryResp::from))
    }

    /// 按逻辑路径浏览目录(前端路径导航用)
    pub async fn list_by_path(
        &self,
        logical_path: &str,
        pagination: &PaginationParams,
        name: Option<&str>,
    ) -> Result<PaginationResponse<FileEntryResp>, AppError> {
        let entry = file_entry_dao::get_by_logical_path(self.db(), logical_path).await?;
        let Some(entry) = entry.filter(|e| e.is_directory) else {
            return Err(AppError::not_found(format!("目录不存在: {logical_path}")));
        };
        self.list_by_pid(Some(&entry.id), pagination, name).await
    }

    /// 按逻辑路径递归创建目录(mkdir -p 语义, 已存在直接返回)
    pub async fn mkdir_p(&self, path: &str, owner_user_id: Option<&str>) -> Result<FileEntryResp, AppError> {
        // 规范化路径: 去首尾斜杠, 拆分层级
        let parts: Vec<&str> = path
            .trim_matches('/')
            .split('/')
            .map(str::trim)
            .filter(|p| !p.is_empty())
            .collect();
        if parts.is_empty() {
            return Err(AppError::business("目录路径不能为空"));
        }
        let mut current_pid: Option<String> = None;
        let mut current_path = String::new();
        let mut entry: Option<FileEntryResp> = None;
        for part in parts {
            // 逐级按完整逻辑路径查询(存在则复用, 不存在则创建)
            current_path = format!("{current_path}/{part}");
            let existing = file_entry_dao::get_by_logical_path(self.db(), &current_path).await?;
            let e = match existing {
                Some(e) if e.is_directory => FileEntryResp::from(e),
                Some(_) => return Err(AppError::conflict(format!("路径 /{part} 已被同名文件占用"))),
                None => {
                    self.create_folder(part.to_string(), current_pid.as_deref(), owner_user_id, None)
                        .await?
                }
            };
            current_pid = Some(e.id.clone());
            entry = Some(e);
        }
        entry.ok_or_else(|| AppError::business("目录路径不能为空"))
    }

    /// 全树模糊搜索(匹配名称或逻辑路径)
    pub async fn search(
        &self,
        keyword: &str,
        pagination: &PaginationParams,
    ) -> Result<PaginationResponse<FileEntryResp>, AppError> {
        let items = file_entry_dao::search(self.db(), keyword, pagination).await?;
        let total = file_entry_dao::count_search(self.db(), keyword).await? as i64;
        Ok(PaginationResponse::create(
            items.into_iter().map(FileEntryResp::from).collect(),
            total,
            pagination,
        ))
    }

    /// 复制条目(文件指向同一内容哈希, 目录递归整树复制)
    pub async fn copy_entry(
        &self,
        entry_id: &str,
        target_pid: Option<String>,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let entry = self.get_active(entry_id).await?;
        self.ensure_module_writable(&entry)?;
        let target_pid = target_pid.filter(|p| !p.is_empty());
        let mut target_path = String::new();
        if let Some(tpid) = &target_pid {
            let target = file_entry_dao::get(self.db(), tpid).await?;
            let Some(target) = target.filter(|e| e.is_active) else {
                return Err(AppError::not_found("目标目录不存在或已被删除"));
            };
            if !target.is_directory {
                return Err(AppError::business("目标条目不是目录"));
            }
            self.ensure_module_writable(&target)?;
            // 环形防护: 目录不能复制到自身子树内
            if entry.is_directory
                && (target.logical_path == entry.logical_path
                    || target.logical_path.starts_with(&format!("{}/", entry.logical_path)))
            {
                return Err(AppError::business("不能复制到自身或其子目录下"));
            }
            target_path = target.logical_path.trim_end_matches('/').to_string();
        }
        // 目标同名冲突校验
        if file_entry_dao::exists_by_pid_name(
            self.db(),
            target_pid.as_deref(),
            &entry.name,
            None,
        )
        .await?
        {
            return Err(AppError::conflict(format!(
                "目标目录下已存在同名条目: {}",
                entry.name
            )));
        }
        self.copy_recursive(&entry, target_pid.as_deref(), &target_path, owner_user_id)
            .await
    }

    /// 递归复制单个条目及其子树(内部方法, 调用方负责冲突/环形校验)
    ///
    /// 递归 async fn 需手动装箱返回值(编译器要求)
    fn copy_recursive<'s>(
        &'s self,
        entry: &'s file_entry::Model,
        target_pid: Option<&'s str>,
        target_path: &'s str,
        owner_user_id: Option<&'s str>,
    ) -> BoxFuture<'s, Result<FileEntryResp, AppError>> {
        Box::pin(self.copy_recursive_inner(entry, target_pid, target_path, owner_user_id))
    }

    async fn copy_recursive_inner(
        &self,
        entry: &file_entry::Model,
        target_pid: Option<&str>,
        target_path: &str,
        owner_user_id: Option<&str>,
    ) -> Result<FileEntryResp, AppError> {
        let new_path = if target_path.is_empty() {
            format!("/{}", entry.name)
        } else {
            format!("{target_path}/{}", entry.name)
        };
        if entry.is_directory {
            let folder_id = file_entry_dao::add(
                self.db(),
                FileEntryCreate {
                    name: entry.name.clone(),
                    pid: target_pid.map(|p| p.to_string()),
                    logical_path: new_path.clone(),
                    is_directory: true,
                    description: entry.description.clone(),
                    source_module: entry.source_module.clone(),
                    user_id: owner_user_id
                        .map(|s| s.to_string())
                        .or_else(|| entry.user_id.clone()),
                    ..Default::default()
                },
            )
            .await?;
            // 递归复制全部直接子项
            let children = file_entry_dao::list_children(self.db(), Some(&entry.id)).await?;
            for child in children {
                self.copy_recursive(&child, Some(&folder_id), &new_path, owner_user_id)
                    .await?;
            }
            return self.get_resp(&folder_id).await;
        }
        // 文件: 新条目指向同一内容哈希, 物理文件不复制
        let file_id = file_entry_dao::add(
            self.db(),
            FileEntryCreate {
                name: entry.name.clone(),
                pid: target_pid.map(|p| p.to_string()),
                logical_path: new_path,
                is_directory: false,
                content_hash: entry.content_hash.clone(),
                file_size_bytes: entry.file_size_bytes.map(|v| v as i64),
                file_extension: entry.file_extension.clone(),
                mime_type: entry.mime_type.clone(),
                description: entry.description.clone(),
                tags: crate::do_::filesystem::json_to_tags(&entry.tags),
                source_module: entry.source_module.clone(),
                user_id: owner_user_id
                    .map(|s| s.to_string())
                    .or_else(|| entry.user_id.clone()),
            },
        )
        .await?;
        file_content_dao::ref_count_change(self.db(), entry.content_hash.as_deref().unwrap_or(""), 1)
            .await?;
        self.get_resp(&file_id).await
    }

    // ==================== 内容级复用方法(跨模块共用) ====================

    /// 按内容哈希查询物理内容记录
    pub async fn get_content(
        &self,
        content_hash: &str,
    ) -> Result<Option<crate::do_::entity::file_content::Model>, AppError> {
        file_content_dao::get_by_content_hash(self.db(), content_hash).await
    }

    /// 内容引用计数+1(业务口径落库后调用, 同时将内容状态置为SUCCESS)
    pub async fn acquire_content(&self, content_hash: &str) -> Result<(), AppError> {
        file_content_dao::ref_count_change(self.db(), content_hash, 1).await
    }

    /// 释放内容引用(计数-1, 归零时清理物理文件与内容记录; 公开口径供业务模块删除时调用)
    pub async fn release_content_public(&self, content_hash: Option<&str>) -> Result<(), AppError> {
        self.release_content(content_hash).await
    }

    /// 读取文件完整字节内容(小文件直接读, 大文件请用 stream_entry_chunks)
    pub async fn read_file_bytes(&self, entry_id: &str) -> Result<Bytes, AppError> {
        let Some((entry, content)) = file_entry_dao::get_with_content(self.db(), entry_id).await?
        else {
            return Err(AppError::not_found(format!("文件不存在: {entry_id}")));
        };
        if !entry.is_active {
            return Err(AppError::not_found(format!("文件不存在: {entry_id}")));
        }
        if entry.is_directory {
            return Err(AppError::business("目录不支持按内容读取"));
        }
        let key = content
            .and_then(|c| c.physical_storage)
            .ok_or_else(|| AppError::business("文件内容记录缺失"))?;
        self.storage().await?.load(&key).await
    }

    /// 读取文本文件内容(默认utf-8)
    pub async fn read_file_text(&self, entry_id: &str) -> Result<String, AppError> {
        let bytes = self.read_file_bytes(entry_id).await?;
        String::from_utf8(bytes.to_vec())
            .map_err(|e| AppError::internal(format!("文本解码失败: {e}")))
    }

    /// 按条目ID流式读取文件内容(跨模块大文件转发用)
    pub async fn stream_entry_chunks(
        &self,
        entry_id: &str,
        chunk_size: usize,
    ) -> Result<BoxStream<'static, Result<Bytes, std::io::Error>>, AppError> {
        let Some((entry, content)) = file_entry_dao::get_with_content(self.db(), entry_id).await?
        else {
            return Err(AppError::not_found(format!("文件不存在: {entry_id}")));
        };
        if !entry.is_active {
            return Err(AppError::not_found(format!("文件不存在: {entry_id}")));
        }
        if entry.is_directory {
            return Err(AppError::business("目录不支持按内容读取"));
        }
        let key = content
            .and_then(|c| c.physical_storage)
            .ok_or_else(|| AppError::business("文件内容记录缺失"))?;
        self.storage().await?.stream(&key, chunk_size).await
    }

    // ==================== 统计/迁移 ====================

    /// 存储统计(条目数/物理内容数/总占用)
    pub async fn get_stats(&self) -> Result<StorageStats, AppError> {
        let (entry_total, file_total, folder_total) = file_entry_dao::count_by_type(self.db()).await?;
        let (content_total, used_bytes) = file_content_dao::stats(self.db()).await?;
        let cfg = self.storage_config().await?;
        Ok(StorageStats {
            // 实际生效的存储类型(启动装配值; 配置中心改类型需重启后此值才变)
            storage_type: cfg.storage_type().as_str().to_string(),
            entry_total,
            file_total,
            folder_total,
            content_total,
            used_bytes,
        })
    }

    /// 存储迁移: 把源存储的全部物理内容搬运到目标存储(逻辑条目与物理键不变)
    pub async fn migrate_storage(&self, req: MigrateRequest) -> Result<MigrateResult, AppError> {
        if req.from_type == req.to_type {
            return Err(AppError::business("源与目标存储类型相同,无需迁移"));
        }
        let src = storage::build_for(&self.state, req.from_type).await?;
        let dst = storage::build_for(&self.state, req.to_type).await?;
        let contents = file_content_dao::list_all(self.db()).await?;
        let mut migrated: i64 = 0;
        let mut skipped: i64 = 0;
        let mut failed = Vec::new();
        for c in &contents {
            // 已在目标存储的内容跳过(支持断点续迁; rustfs 落库记 S3, 行为复用 S3 口径)
            if c.storage_type.as_ref().map(storage_type_enum_str) == Some(req.to_type.as_str()) {
                skipped += 1;
                continue;
            }
            let outcome: Result<(), AppError> = async {
                let key = c
                    .physical_storage
                    .clone()
                    .ok_or_else(|| AppError::internal("内容记录缺少物理存储键"))?;
                let data = src.load(&key).await?;
                dst.save(&key, &data).await?;
                // 更新内容记录的存储类型(物理键不变)
                file_content_dao::update(
                    self.db(),
                    &c.content_hash,
                    FileContentPatch {
                        storage_type: Some(db_storage_enum(req.to_type)),
                        ..Default::default()
                    },
                )
                .await?;
                Ok(())
            }
            .await;
            match outcome {
                Ok(()) => migrated += 1,
                Err(e) => {
                    tracing::error!("迁移失败 {}: {e}", c.content_hash);
                    failed.push(crate::do_::filesystem::MigrateItemError {
                        content_hash: c.content_hash.clone(),
                        error: e.to_string(),
                    });
                }
            }
        }
        tracing::info!(
            "存储迁移完成: {}->{} migrated={migrated} skipped={skipped} failed={}",
            req.from_type.as_str(),
            req.to_type.as_str(),
            failed.len()
        );
        Ok(MigrateResult {
            total: contents.len(),
            migrated,
            skipped,
            failed,
        })
    }
}

/// 判断用户对条目是否有下载权限(不抛异常, 下载鉴权与批量探测共用)
///
/// 判定顺序: 目录不可下载 → avatar 公开 → 登录持 main:file:download → 业务模块注册的授权钩子
pub async fn can_download_entry(
    _state: &AppState,
    user_id: Option<&str>,
    entry: &file_entry::Model,
) -> bool {
    if entry.is_directory {
        return false;
    }
    if entry.source_module.as_deref() == Some("avatar") {
        return true;
    }
    let Some(uid) = user_id else {
        return false;
    };
    if module_authorization::deps::authorize(uid, "main", "file", "download")
        .await
        .is_ok()
    {
        return true;
    }
    // 业务条目(source_module 标记)交由来源模块注册的授权钩子判定(rag: 项目 editor 档位放行)
    if let Some(m) = &entry.source_module {
        if m != "file" {
            if let Some(grant) = download_grant::get_download_grant(m) {
                if grant(uid.to_string(), entry.clone()).await {
                    return true;
                }
            }
        }
    }
    false
}

/// 下载鉴权依赖(对齐 Python get_download_user_id)
///
/// - 匿名: 仅放行 avatar 来源公开条目, 其余 401
/// - 已登录无权限: 403(与未登录区分, 供前端提示)
/// - 条目不存在: 404
pub async fn check_download_access(
    state: &AppState,
    entry_id: &str,
    user_id: Option<String>,
) -> Result<file_entry::Model, AppError> {
    let entry = file_entry_dao::get(&state.db, entry_id).await?;
    let Some(entry) = entry else {
        return Err(AppError::not_found("文件或目录不存在"));
    };
    if can_download_entry(state, user_id.as_deref(), &entry).await {
        return Ok(entry);
    }
    if user_id.is_some() {
        return Err(AppError::forbidden("无下载权限"));
    }
    Err(AppError::unauthorized("未登录或无下载权限"))
}

/// 恒定时间字符串比较(签名校验用)
fn subtle_equal(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    a.bytes().zip(b.bytes()).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

/// 存储类型 → 内容表枚举(共享库口径: rustfs 行为复用 S3、落库记 S3)
fn db_storage_enum(t: StorageType) -> Storagetype {
    match t {
        StorageType::Local => Storagetype::Local,
        StorageType::S3 | StorageType::Rustfs => Storagetype::S3,
    }
}
