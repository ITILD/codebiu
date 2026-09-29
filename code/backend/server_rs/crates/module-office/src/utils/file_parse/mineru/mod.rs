//! MinerU 解析引擎(对齐 Python utils/file_parase/mineru/)。
//!
//! 支持两种部署(配置 mineru.mode):
//! - remote(默认): mineru.net 远程 API v4, 支持批量解析
//! - local: 本地 docker 部署的 mineru-api

pub mod client;
pub mod parser;
