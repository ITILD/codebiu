// src/modules/rag/api/user_model.ts
// 用户-模型绑定 API(对应后端 /rag/user-models/*, v4 4.3)
import { http_base_server } from '@/common/api/http';

/** 当前用户模型绑定(未绑定字段为 null) */
export interface UserModelBinding {
  id: string;
  user_id: string;
  /** 绑定的对话模型配置ID */
  chat_model_id: string | null;
  /** 绑定的向量化模型配置ID */
  embedding_model_id: string | null;
  /** 绑定的重排模型配置ID */
  rerank_model_id: string | null;
  /** 回退开关: true=绑定失效时不回退默认公共模型(直接报错) */
  fallback_disabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** 更新模型绑定载荷(仅提交的字段生效; 显式 null 表示解绑) */
export interface UserModelBindingUpdate {
  chat_model_id?: string | null;
  embedding_model_id?: string | null;
  rerank_model_id?: string | null;
  fallback_disabled?: boolean;
}

/**
 * 获取当前用户的模型绑定(未绑定时返回空绑定结构)
 * @returns 用户模型绑定详情
 */
export const getMyModelBinding = () => {
  return http_base_server.get<UserModelBinding>('/rag/user-models/my');
};

/**
 * 更新当前用户的模型绑定(绑定前校验模型归属: 公共/本部门/本人模型)
 * @param payload 更新载荷(未提交字段保持原值; 模型ID传 null 解绑)
 * @returns 更新后的绑定详情
 */
export const updateMyModelBinding = (payload: UserModelBindingUpdate) => {
  return http_base_server.put<UserModelBinding>('/rag/user-models/my', payload);
};
