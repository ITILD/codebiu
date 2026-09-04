// src/api/main/status.ts
// 服务器状态接口(对应后端 /server_status)
import { http_base_server } from '@/utils/http';
import type {
  HardwareStatus,
  NetworkStatus,
  StatusServer,
} from '@/types/main/status';

/** 获取主机状态60秒缓存(硬件+网络聚合) */
export const getStatusCache = () => {
  return http_base_server.get<StatusServer>('/server_status/status_cache');
};

/** 获取主机型号(平台标识) */
export const getSysInfo = () => {
  return http_base_server.get<string>('/server_status/sys_info');
};

/** 实时获取硬件状态(CPU/内存/磁盘/GPU) */
export const getHardwareStatus = () => {
  return http_base_server.get<HardwareStatus>('/server_status/hardware_status');
};

/** 实时获取网络状态 */
export const getNetworkStatus = () => {
  return http_base_server.get<NetworkStatus[]>('/server_status/network_status');
};

/** 查看 app 挂载路由数量 */
export const getMountCount = () => {
  return http_base_server.get<unknown[]>('/server_status/mount_count');
};
