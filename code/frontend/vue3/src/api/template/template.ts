// src/api/template.ts
import { http_base_server } from '@/utils/http';
import {
  type InfiniteScrollParams,
  type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { Template, TemplateCreate, TemplateUpdate } from '@/types/template/template';

/**
 * 创建新模板
 * @param template 模板数据
 * @returns 创建的模板ID
 */
export const createTemplate = (template: TemplateCreate) => {
  return http_base_server.post<object>('/template/templates', template);
};

/**
 * 删除模板
 * @param templateId 模板ID
 */
export const deleteTemplate = (templateId: string) => {
  return http_base_server.delete<void>(`/template/templates/${templateId}`);
};

/**
 * 更新模板
 * @param templateId 模板ID
 * @param template 模板数据
 */
export const updateTemplate = (templateId: string, template: TemplateUpdate) => {
  return http_base_server.put<void>(`/template/templates/${templateId}`, template);
};

/**
 * 获取单个模板详情
 * @param templateId 模板ID
 * @returns 模板详情
 */
export const getTemplate = (templateId: string) => {
  return http_base_server.get<Template>(`/template/templates/${templateId}`);
};

/**
 * 分页查询模板列表
 * @param params 分页参数
 * @returns 分页响应结果
 */
export const listTemplates = (params: PaginationParams) => {
  return http_base_server.get<PaginationResponse<Template>>('/template/templates/list', { params });
};

/**
 * 无限滚动加载模板列表
 * @param params 滚动加载参数
 * @returns 滚动加载响应结果
 */
export const infiniteScrollTemplates = (params: InfiniteScrollParams) => {
  return http_base_server.get<InfiniteScrollResponse<Template>>('/template/templates/scroll', {
    params
  });
};