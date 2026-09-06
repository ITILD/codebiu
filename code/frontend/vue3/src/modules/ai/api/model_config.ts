// src/modules/ai/api/model_config.ts
import { http_base_server } from '@/common/api/http';
import {
  type InfiniteScrollParams,
  type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/common/types/common';
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '../types/model_config';

/**
 * 创建新模型配置
 * @param modelConfig 模型配置数据
 * @returns 创建的模型配置ID
 */
export const createModelConfig = (modelConfig: ModelConfigCreate) => {
  return http_base_server.post<object>('/ai/model-configs', modelConfig);
};

/**
 * 删除模型配置
 * @param modelConfigId 模型配置ID
 */
export const deleteModelConfig = (modelConfigId: string) => {
  return http_base_server.delete<void>(`/ai/model-configs/${modelConfigId}`);
};

/**
 * 更新模型配置
 * @param modelConfigId 模型配置ID
 * @param modelConfig 模型配置数据
 */
export const updateModelConfig = (modelConfigId: string, modelConfig: ModelConfigUpdate) => {
  return http_base_server.put<void>(`/ai/model-configs/${modelConfigId}`, modelConfig);
};

/**
 * 获取单个模型配置详情
 * @param modelConfigId 模型配置ID
 * @returns 模型配置详情
 */
export const getModelConfig = (modelConfigId: string) => {
  return http_base_server.get<ModelConfig>(`/ai/model-configs/${modelConfigId}`);
};

/**
 * 分页查询模型配置列表
 * @param params 分页参数
 * @returns 分页响应结果
 */
export const listModelConfigs = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<ModelConfig>>('/ai/model-configs/list', { params });
};

/**
 * 无限滚动加载模型配置列表
 * @param params 滚动加载参数
 * @returns 滚动加载响应结果
 */
export const infiniteScrollModelConfigs = (params: InfiniteScrollParams) => {
  return http_base_server.get<InfiniteScrollResponse<ModelConfig>>('/ai/model-configs/scroll', {
    params
  });
};

/**
 * 提交全库 chunk 重向量化任务(系统管理员)
 * 以指定/当前生效的默认公共向量化模型, 重算 Milvus 中所有 chunk 向量
 * @param modelId 目标模型配置ID(留空使用当前生效的默认公共向量化模型)
 * @returns Celery 任务ID
 */
export const revectorizeChunks = (modelId?: string) => {
  return http_base_server.post<{ task_id: string; message: string }>(
    '/rag/project-document-chunks/revectorize',
    { model_id: modelId || null }
  );
};

/**
 * 查询全库重向量化任务进度(系统管理员)
 * @param taskId POST /revectorize 返回的任务ID
 * @returns state=PROGRESS 时 meta 含 total/processed/chunks/model
 */
export const getRevectorizeStatus = (taskId: string) => {
  return http_base_server.get<{
    task_id: string;
    state: string;
    meta?: { total: number; processed: number; chunks: number; model: string; dim_changed: boolean };
    error?: string;
  }>(`/rag/project-document-chunks/revectorize/status/${taskId}`);
};