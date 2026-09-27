//! 用户头像服务(对齐 Python module_authorization/service/avatar.py)
//!
//! 因 Rust 侧依赖方向为 module-file → module-authorization(不可反向),
//! 头像服务实现置于 module-file, 由 app 以 `/authorization` 前缀挂载 avatar 路由,
//! 契约路径与 Python 完全一致: /authorization/auth/me/avatar

use bytes::Bytes;

use common::runtime::AppState;
use common::utils::error::AppError;
use serde::Serialize;

use crate::services::filesystem::FileService;

/// 头像模块在虚拟目录树中的模块根(source_module 标记; 该标记条目允许匿名下载)
pub const AVATAR_MODULE_KEY: &str = "avatar";
pub const AVATAR_MODULE_LABEL: &str = "用户头像";

/// 允许上传的图片扩展名(不含点)
pub const ALLOWED_IMAGE_EXTS: [&str; 7] = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"];

/// 头像上传响应(对齐 Python {"avatar": 下载路径, "entry_id": 条目ID})
#[derive(Debug, Serialize)]
pub struct AvatarUploadResp {
    pub avatar: String,
    pub entry_id: String,
}

/// 用户头像服务(注入统一文件服务, 头像文件存于虚拟目录 /用户头像/ 下)
pub struct AvatarService {
    state: AppState,
}

impl AvatarService {
    pub fn new(state: AppState) -> Self {
        Self { state }
    }

    /// 统一文件服务(业务口径, 无业务条目只读拦截)
    fn file_service(&self) -> FileService {
        FileService::new(self.state.clone(), false)
    }

    /// 从历史头像字段解析文件条目ID(仅识别本服务写入的下载路径/裸条目ID格式)
    ///
    /// 对齐 Python: 正则 `/file/filesystem/download/([0-9a-f]{32})$` 或裸 32 位小写 hex
    fn extract_entry_id(avatar: Option<&str>) -> Option<String> {
        let avatar = avatar?;
        const MARK: &str = "/file/filesystem/download/";
        if let Some(pos) = avatar.find(MARK) {
            let tail = &avatar[pos + MARK.len()..];
            if tail.len() == 32 && tail.chars().all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c)) {
                return Some(tail.to_string());
            }
        }
        if avatar.len() == 32
            && avatar
                .chars()
                .all(|c| c.is_ascii_digit() || ('a'..='f').contains(&c))
        {
            return Some(avatar.to_string());
        }
        None
    }

    /// 上传用户头像: 经统一文件服务存入 /用户头像/<用户ID>/ 并回写用户头像字段
    pub async fn upload_avatar(
        &self,
        user_id: &str,
        filename: &str,
        content: Bytes,
    ) -> Result<AvatarUploadResp, AppError> {
        let filename = if filename.is_empty() { "avatar.png" } else { filename };
        let ext = std::path::Path::new(filename)
            .extension()
            .map(|e| e.to_string_lossy().to_lowercase())
            .unwrap_or_default();
        if !ALLOWED_IMAGE_EXTS.contains(&ext.as_str()) {
            // 与 Python sorted + '/' join 的提示文案一致
            let mut allowed = ALLOWED_IMAGE_EXTS.to_vec();
            allowed.sort_unstable();
            return Err(AppError::business(format!(
                "不支持的图片格式 '{ext}', 允许: {}",
                allowed.join("/")
            )));
        }
        let fs = self.file_service();
        // 幂等确保头像模块根目录与用户专属子目录
        let root = fs
            .ensure_module_root(AVATAR_MODULE_KEY, AVATAR_MODULE_LABEL, Some(user_id))
            .await?;
        let folder = fs
            .ensure_folder(user_id, Some(&root.id), Some(user_id))
            .await?;
        // 上传新头像(内容哈希去重, 内容引用计数由文件条目维护)
        let entry = fs
            .upload_file(
                filename,
                content,
                Some("用户头像"),
                Some(&folder.id),
                Some(user_id),
            )
            .await?;
        // 删除旧头像条目(仅当其属于 avatar 模块, 防止误删外部链接指向的条目)
        let old = module_authorization::dao::user::get(&self.state.db, user_id).await;
        let old_entry_id = Self::extract_entry_id(old.as_ref().and_then(|u| u.avatar.as_deref()));
        if let Some(old_id) = old_entry_id {
            if old_id != entry.id {
                if let Some(old_entry) = fs.get_file_entry(&old_id).await? {
                    if old_entry.source_module.as_deref() == Some(AVATAR_MODULE_KEY) {
                        if let Err(e) = fs.delete_file(&old_id).await {
                            tracing::warn!("清理旧头像条目失败 {old_id}: {e}");
                        }
                    }
                }
            }
        }
        // 头像字段存 API 下载路径(匿名可访问, 前端 <img> 直接可用)
        let avatar_url = format!("/base_server/file/filesystem/download/{}", entry.id);
        module_authorization::dao::user::update_avatar(&self.state.db, user_id, Some(avatar_url.clone()))
            .await?;
        Ok(AvatarUploadResp {
            avatar: avatar_url,
            entry_id: entry.id,
        })
    }

    /// 删除当前头像还原默认(用户名首字头像): 清理 avatar 模块条目并置空用户头像字段
    pub async fn delete_avatar(&self, user_id: &str) -> Result<(), AppError> {
        let user = module_authorization::dao::user::get(&self.state.db, user_id).await;
        let Some(avatar) = user.as_ref().and_then(|u| u.avatar.clone()).filter(|a| !a.is_empty())
        else {
            return Err(AppError::business("当前未设置头像"));
        };
        let fs = self.file_service();
        // 清理 avatar 模块的头像文件条目(仅识别本服务写入的格式, 外部链接不动)
        if let Some(entry_id) = Self::extract_entry_id(Some(&avatar)) {
            if let Some(entry) = fs.get_file_entry(&entry_id).await? {
                if entry.source_module.as_deref() == Some(AVATAR_MODULE_KEY) {
                    if let Err(e) = fs.delete_file(&entry_id).await {
                        tracing::warn!("清理头像条目失败 {entry_id}: {e}");
                    }
                }
            }
        }
        // 置空头像字段, 前端回退为用户名首字默认头像
        module_authorization::dao::user::update_avatar(&self.state.db, user_id, None).await?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn 提取头像条目ID() {
        assert_eq!(
            AvatarService::extract_entry_id(Some("/base_server/file/filesystem/download/0123456789abcdef0123456789abcdef")),
            Some("0123456789abcdef0123456789abcdef".to_string())
        );
        assert_eq!(
            AvatarService::extract_entry_id(Some("0123456789abcdef0123456789abcdef")),
            Some("0123456789abcdef0123456789abcdef".to_string())
        );
        // 大写 hex / 非32位 / 空值均不识别
        assert_eq!(AvatarService::extract_entry_id(Some("0123456789ABCDEF0123456789ABCDEF")), None);
        assert_eq!(AvatarService::extract_entry_id(Some("/other/path")), None);
        assert_eq!(AvatarService::extract_entry_id(None), None);
    }
}
