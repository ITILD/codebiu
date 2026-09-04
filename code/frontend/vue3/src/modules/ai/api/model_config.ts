// src/api/model_config.ts
import { http_base_server } from '@/utils/http';
import {
  type InfiniteScrollParams,
  type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types/model_config';

/**
 * 创建新模型配置
 * @param modelConfig 模型配置数据
 * @returns 创建的模型配置ID
 */
export const createModelConfig = (modelConfig: ModelConfigCreate) => {
  return http_base_server.post<object>('/ai/model_config', modelConfig);
};

/**
 * 删除模型配置
 * @param modelConfigId 模型配置ID
 */
export const deleteModelConfig = (modelConfigId: string) => {
  return http_base_server.delete<void>(`/ai/model_config/${modelConfigId}`);
};

/**
 * 更新模型配置
 * @param modelConfigId 模型配置ID
 * @param modelConfig 模型配置数据
 */
export const updateModelConfig = (modelConfigId: string, modelConfig: ModelConfigUpdate) => {
  return http_base_server.put<void>(`/ai/model_config/${modelConfigId}`, modelConfig);
};

/**
 * 获取单个模型配置详情
 * @param modelConfigId 模型配置ID
 * @returns 模型配置详情
 */
export const getModelConfig = (modelConfigId: string) => {
  return http_base_server.get<ModelConfig>(`/ai/model_config/${modelConfigId}`);
};

/**
 * 分页查询模型配置列表
 * @param params 分页参数
 * @returns 分页响应结果
 */
export const listModelConfigs = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<ModelConfig>>('/ai/model_config/list', { params });
};

/**
 * 无限滚动加载模型配置列表
 * @param params 滚动加载参数
 * @returns 滚动加载响应结果
 */
export const infiniteScrollModelConfigs = (params: InfiniteScrollParams) => {
  return http_base_server.get<InfiniteScrollResponse<ModelConfig>>('/ai/model_config/scroll', {
    params
  });
};