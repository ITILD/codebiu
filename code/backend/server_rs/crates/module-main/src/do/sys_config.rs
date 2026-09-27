//! 系统通用动态配置数据对象(对齐 Python module_main/do/sys_config.py)

use serde::Deserialize;

/// 配置组更新请求体(对齐 ConfigUpdateRequest): data 为该组字段的(嵌套)dict
#[derive(Debug, Deserialize)]
pub struct ConfigUpdateRequest {
    #[serde(default)]
    pub data: serde_json::Value,
}
