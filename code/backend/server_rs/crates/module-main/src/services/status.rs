//! 主机状态服务(对齐 Python service/status.py + common/utils/sys/status.py)
//!
//! 采集硬件(CPU/内存/磁盘/GPU)/网络连通性/平台信息, status_cache 提供 60 秒 TTL 缓存。

use std::time::{Duration, Instant};

use crate::do_::status::{CpuInfo, DiskInfo, GpuInfo, HardwareStatus, MemoryInfo, NetworkStatus, StatusServer};

/// 字节 → GB(保留两位, 对齐 Python SystemMonitor.b2gb)
fn b2gb(bytes: f64) -> f64 {
    (bytes / (1024f64 * 1024f64 * 1024f64) * 100.0).round() / 100.0
}

/// 百分比保留两位
fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

/// 主机状态单例(对齐 Python get_status_service_singleton)
pub fn service() -> &'static StatusService {
    static STATUS: std::sync::OnceLock<StatusService> = std::sync::OnceLock::new();
    STATUS.get_or_init(|| StatusService { cache: std::sync::Mutex::new(None) })
}

/// 主机状态服务
pub struct StatusService {
    /// 60s TTL 缓存(值: 采集时刻 + 综合状态)
    cache: std::sync::Mutex<Option<(Instant, StatusServer)>>,
}

impl StatusService {
    /// 一分钟一次获取系统状态(缓存未过期直接返回)
    pub async fn status_cache(&self, http: &reqwest::Client) -> StatusServer {
        if let Some((at, cached)) = self.cache.lock().expect("状态缓存锁").clone() {
            if at.elapsed() < Duration::from_secs(60) {
                return cached;
            }
        }
        let hardware = hardware_status().await;
        let network = network_status(http).await;
        let status =
            StatusServer { hardware: Some(hardware), network: Some(network) };
        *self.cache.lock().expect("状态缓存锁") = Some((Instant::now(), status.clone()));
        status
    }
}

/// 采集硬件状态(CPU/内存/磁盘/GPU; CPU 使用率需两次采样, 与 Python 一致等待 1 秒)
pub async fn hardware_status() -> HardwareStatus {
    let mut sys = sysinfo::System::new();
    sys.refresh_cpu_usage();
    tokio::time::sleep(Duration::from_millis(1000)).await;
    sys.refresh_cpu_usage();
    sys.refresh_memory();

    let threads = sys.cpus().len();
    let cores = sys.physical_core_count().unwrap_or(threads);
    let cpu = CpuInfo {
        percent: round2(sys.global_cpu_usage() as f64),
        cores,
        threads,
    };
    let total = sys.total_memory() as f64;
    let used = sys.used_memory() as f64;
    let memory = MemoryInfo {
        total: b2gb(total),
        used: b2gb(used),
        percent: if total > 0.0 { round2(used / total * 100.0) } else { 0.0 },
    };
    let disk = disk_info().await;
    let gpu = gpu_info().await;
    HardwareStatus {
        disk,
        memory,
        cpu,
        gpu,
        timestamp: chrono::Local::now().naive_local(),
    }
}

/// 获取主机平台信息(系统/架构, 对齐 Python PlatformUtils.get_platform_id)
pub fn sys_info() -> String {
    let system = match std::env::consts::OS {
        "windows" => "win",
        "macos" => "osx",
        "linux" => "linux",
        other => other,
    };
    let machine = match std::env::consts::ARCH {
        "x86_64" | "AMD64" => "x64",
        "x86" | "i386" | "i686" => "x86",
        "aarch64" | "arm64" => "arm64",
        other => other,
    };
    format!("{system}-{machine}")
}

/// 磁盘信息(psutil.disk_usage("/") 等价: unix 取根挂载, 其余取第一块盘)
async fn disk_info() -> DiskInfo {
    let disks = sysinfo::Disks::new_with_refreshed_list();
    let disk = disks
        .list()
        .iter()
        .find(|d| d.mount_point() == std::path::Path::new("/"))
        .or_else(|| disks.list().first());
    match disk {
        Some(d) => {
            let total_bytes = d.total_space();
            let used_bytes = total_bytes.saturating_sub(d.available_space());
            DiskInfo {
                total: b2gb(total_bytes as f64),
                used: b2gb(used_bytes as f64),
                percent: if total_bytes > 0 { round2(used_bytes as f64 / total_bytes as f64 * 100.0) } else { 0.0 },
            }
        }
        None => DiskInfo { total: 0.0, used: 0.0, percent: 0.0 },
    }
}

/// GPU 信息(自动检测 NVIDIA 或 AMD, NVIDIA 优先; 未检测到返回空列表)
async fn gpu_info() -> Vec<GpuInfo> {
    let nvidia = nvidia_gpu_info().await;
    if !nvidia.is_empty() {
        return nvidia;
    }
    amd_gpu_info().await
}

/// 使用 nvidia-smi 获取 NVIDIA GPU 信息(失败返回空列表)
async fn nvidia_gpu_info() -> Vec<GpuInfo> {
    let Ok(out) = tokio::process::Command::new("nvidia-smi")
        .args([
            "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .await
    else {
        return Vec::new();
    };
    if !out.status.success() {
        return Vec::new();
    }
    let text = String::from_utf8_lossy(&out.stdout);
    let mut gpus = Vec::new();
    for line in text.trim().lines() {
        let values: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
        if values.len() < 6 {
            continue;
        }
        gpus.push(GpuInfo {
            vendor: "NVIDIA",
            id: values[0].parse().unwrap_or(0),
            name: values[1].to_string(),
            total: values[2].parse().unwrap_or(0.0),
            used: values[3].parse().unwrap_or(0.0),
            percent: values[4].parse().unwrap_or(0.0),
            temp: values[5].parse().unwrap_or(0.0),
        });
    }
    gpus
}

/// 使用 rocm-smi 获取 AMD GPU 信息(失败返回空列表)
async fn amd_gpu_info() -> Vec<GpuInfo> {
    let Ok(out) = tokio::process::Command::new("rocm-smi")
        .args(["--showmeminfo", "vram", "--showtemp", "--showuse", "--json"])
        .output()
        .await
    else {
        return Vec::new();
    };
    let Ok(data) = serde_json::from_slice::<serde_json::Value>(&out.stdout) else {
        return Vec::new();
    };
    let Some(obj) = data.as_object() else { return Vec::new() };
    // JSON 数值/字符串统一转 f64(rocm 输出多为字符串)
    fn jf(v: &serde_json::Value) -> f64 {
        match v {
            serde_json::Value::Number(n) => n.as_f64().unwrap_or(0.0),
            serde_json::Value::String(s) => s.trim().parse().unwrap_or(0.0),
            _ => 0.0,
        }
    }
    let mut gpus = Vec::new();
    for (key, gpu_data) in obj {
        if !key.starts_with("card") {
            continue;
        }
        gpus.push(GpuInfo {
            vendor: "AMD",
            id: gpu_data.get("Device Number").map(jf).unwrap_or(0.0) as i64,
            name: gpu_data
                .get("Device Name")
                .and_then(|v| v.as_str())
                .unwrap_or_default()
                .to_string(),
            total: b2gb(gpu_data.pointer("/vram/Total Memory (B)").map(jf).unwrap_or(0.0)),
            used: b2gb(gpu_data.pointer("/vram/Used Memory (B)").map(jf).unwrap_or(0.0)),
            percent: round2(gpu_data.get("GPU use (%)").map(jf).unwrap_or(0.0)),
            temp: round2(gpu_data.get("Temperature (C)").map(jf).unwrap_or(0.0)),
        });
    }
    gpus
}

/// 并发探测指定URL列表的连通性(默认探测常用站点; 10 秒超时)
pub async fn network_status(http: &reqwest::Client) -> Vec<NetworkStatus> {
    let urls = [
        "https://www.baidu.com",
        "http://example.com",
        "https://github.com",
        "http://www.google.com",
    ];
    // 并发探测(spawn 保序拼接)
    let mut handles = Vec::with_capacity(urls.len());
    for (idx, url) in urls.iter().enumerate() {
        let client = http.clone();
        let url = url.to_string();
        handles.push(tokio::spawn(async move {
            let ok = fetch_title(&client, &url).await.is_some();
            (idx, NetworkStatus { url, connect_success: ok })
        }));
    }
    let mut results = Vec::with_capacity(urls.len());
    for handle in handles {
        if let Ok(pair) = handle.await {
            results.push(pair);
        }
    }
    results.sort_by_key(|(idx, _)| *idx);
    results.into_iter().map(|(_, status)| status).collect()
}

/// 请求页面并提取 <title>(连接失败/无 title 均视为 None, 对齐 WebConnectTestNative.fetch_title_timeout)
async fn fetch_title(http: &reqwest::Client, url: &str) -> Option<String> {
    let body = http
        .get(url)
        .timeout(Duration::from_secs(10))
        .send()
        .await
        .ok()?
        .text()
        .await
        .ok()?;
    let start = body.find("<title>")?;
    let from = start + "<title>".len();
    let end = body[from..].find("</title>")? + from;
    Some(body[from..end].chars().take(50).collect())
}
