// src/modules/main/api/sys_config.ts
// 系统通用动态配置接口(对应后端 /sys-configs)
// 密钥字段只回 has_value(不回显明文), 更新时缺省保持/空串清除
import { http_base_server } from '@/common/api/http';

/** 配置字段元数据(由后端 schema 声明推导, 新增配置组前端零改动) */
export interface ConfigField {
  /** 字段键(嵌套子组字段为点路径, 如 "tavily.api_key") */
  key: string;
  /** 展示标题 */
  title: string;
  /** 字段说明 */
  description: string;
  /** 表单控件类型 */
  type: 'str' | 'int' | 'float' | 'bool' | 'enum' | 'list' | 'secret';
  /** enum 控件的可选值 */
  options?: string[] | null;
  /** 是否必填 */
  required?: boolean;
  /** 当前值(密钥字段为 null) */
  value?: unknown;
  /** 密钥字段是否已配置 */
  has_value?: boolean;
}

/** 配置组描述(组元数据 + 字段元数据 + 打码值) */
export interface ConfigGroup {
  /** 组标识(与后端 yaml/sys_config 表 group 一致) */
  group: string;
  /** 组展示名 */
  name: string;
  /** 组说明 */
  description: string;
  /** 是否需要重启才能生效(连接级配置) */
  restart_required: boolean;
  /** 最近更新时间(ISO; 未更新过为 null) */
  updated_at: string | null;
  /** 最近更新人 */
  updated_by: string | null;
  /** 字段元数据列表 */
  fields: ConfigField[];
}

/** 获取全部配置组(元数据+打码值) */
export const listSysConfigs = () => {
  return http_base_server.get<{ groups: ConfigGroup[] }>('/sys-configs');
};

/** 获取单个配置组 */
export const getSysConfig = (group: string) => {
  return http_base_server.get<ConfigGroup>(`/sys-configs/${group}`);
};

/** 更新配置组(data 为嵌套字段键值; 密钥缺省保持, 空串清除) */
export const updateSysConfig = (group: string, data: Record<string, unknown>) => {
  return http_base_server.put<void>(`/sys-configs/${group}`, { data });
};
