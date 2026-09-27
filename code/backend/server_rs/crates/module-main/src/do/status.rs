//! 主机状态数据对象(对齐 Python module_main/do/status.py)

use serde::Serialize;

/// 磁盘信息(单位 GB)
#[derive(Debug, Clone, Serialize)]
pub struct DiskInfo {
    pub total: f64,
    pub used: f64,
    pub percent: f64,
}

/// 内存信息(单位 GB)
#[derive(Debug, Clone, Serialize)]
pub struct MemoryInfo {
    pub total: f64,
    pub used: f64,
    pub percent: f64,
}

/// CPU 信息
#[derive(Debug, Clone, Serialize)]
pub struct CpuInfo {
    /// CPU 使用率百分比
    pub percent: f64,
    /// 物理核心数
    pub cores: usize,
    /// 逻辑线程数
    pub threads: usize,
}

/// GPU 信息(显存单位 MB)
#[derive(Debug, Clone, Serialize)]
pub struct GpuInfo {
    /// GPU 厂商(NVIDIA 或 AMD)
    pub vendor: &'static str,
    pub id: i64,
    pub name: String,
    pub total: f64,
    pub used: f64,
    /// 显存使用率百分比
    pub percent: f64,
    /// GPU 温度(°C)
    pub temp: f64,
}

/// 硬件状态(对齐 common/utils/sys/do/status.HardwareStatus)
#[derive(Debug, Clone, Serialize)]
pub struct HardwareStatus {
    pub disk: DiskInfo,
    pub memory: MemoryInfo,
    pub cpu: CpuInfo,
    pub gpu: Vec<GpuInfo>,
    /// 采集时间戳(本地时间)
    pub timestamp: chrono::NaiveDateTime,
}

/// 网络连通状态(对齐 NetworkStatus)
#[derive(Debug, Clone, Serialize)]
pub struct NetworkStatus {
    pub url: String,
    pub connect_success: bool,
}

/// 主机综合状态(对齐 StatusServer)
#[derive(Debug, Clone, Serialize)]
pub struct StatusServer {
    pub hardware: Option<HardwareStatus>,
    pub network: Option<Vec<NetworkStatus>>,
}
