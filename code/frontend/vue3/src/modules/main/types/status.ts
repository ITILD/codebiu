// src/modules/main/types/status.ts
// 对应后端 module_main 的 /server_status 接口数据结构

/** 磁盘信息 */
export type DiskInfo = {
  total: number // 单位: GB
  used: number // 单位: GB
  percent: number // 百分比
}

/** 内存信息 */
export type MemoryInfo = {
  total: number // 单位: GB
  used: number // 单位: GB
  percent: number // 百分比
}

/** CPU 信息 */
export type CPUInfo = {
  percent: number // CPU 使用率百分比
  cores: number // 物理核心数
  threads: number // 逻辑线程数
}

/** GPU 信息 */
export type GPUInfo = {
  vendor: string // GPU 厂商(NVIDIA 或 AMD)
  id: number // GPU ID
  name: string // GPU 名称
  total: number // 显存总量(单位: MB)
  used: number // 已用显存(单位: MB)
  percent: number // 显存使用率百分比
  temp: number // GPU 温度(单位: °C)
}

/** 硬件状态 */
export type HardwareStatus = {
  disk: DiskInfo
  memory: MemoryInfo
  cpu: CPUInfo
  gpu: GPUInfo[]
  timestamp: string
}

/** 网络状态 */
export type NetworkStatus = {
  url: string
  connect_success: boolean
}

/** 服务器状态(60秒缓存聚合数据) */
export type StatusServer = {
  hardware: HardwareStatus | null
  network: NetworkStatus[] | null
}
