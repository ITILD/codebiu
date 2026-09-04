// src/modules/rag/types/index.ts
// 知识库(RAG)模块类型定义
import type { MessageBlock } from '@/common/types/chat';

// 知识库分类: 个人/项目/公司
enum KbCategory {
  PERSONAL = 'personal',
  PROJECT = 'project',
  COMPANY = 'company',
}

// 项目级角色
enum RagRole {
  PROJECT_ADMIN = 'project_admin',
  PROJECT_EDITOR = 'project_editor',
  PROJECT_READER = 'project_reader',
}

// ---------------- 项目 ----------------

interface Project {
  id: string;
  name: string;
  description?: string | null;
  is_private: boolean;
  kb_category: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface ProjectCreate {
  name: string;
  description?: string | null;
  is_private?: boolean;
  kb_category?: string;
}

interface ProjectUpdate {
  name?: string;
  description?: string | null;
  is_private?: boolean;
  kb_category?: string;
}

// ---------------- 项目文档 ----------------

// 文档解析状态: 待解析/解析中/已完成/解析失败
enum ParseStatus {
  PENDING = 'pending',
  PARSING = 'parsing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

interface ProjectDocument {
  id: string;
  project_id: string;
  name: string;
  file_extension: string;
  mime_type?: string | null;
  file_size_bytes: number;
  physical_path: string;
  description?: string | null;
  uploaded_by: string;
  created_at: string;
  updated_at: string;
  /** 解析状态: pending/parsing/completed/failed */
  parse_status?: string;
  /** 解析生成的分块数量 */
  chunk_count?: number;
  /** 解析失败原因 */
  error_message?: string | null;
}

interface ProjectDocumentUpdate {
  name?: string;
  description?: string | null;
}

// 支持的上传类型分组
interface SupportedFileTypes {
  documents: string[];
  images: string[];
  audios: string[];
  videos: string[];
  all_extensions: string[];
}

// ---------------- 项目成员 ----------------

interface ProjectMember {
  id: string;
  user_id: string;
  project_id: string;
  role: string;
  created_at: string;
  updated_at: string;
}

interface ProjectMemberCreate {
  user_id: string;
  project_id: string;
  role: string;
}

interface ProjectMemberUpdate {
  role?: string;
}

interface MyProject {
  project_id: string;
  project_name: string;
  project_description?: string | null;
  is_private: boolean;
  kb_category: string;
  role: string;
  created_at: string;
}

// ---------------- 项目部门授权 ----------------

// 部门授权生效规则: 用户生效档位 = max(直连成员档位, 部门链命中最高档)
interface ProjectDept {
  id: string;
  project_id: string;
  dept_id: string;
  role: string;
  created_at: string;
  updated_at: string;
}

interface ProjectDeptCreate {
  project_id: string;
  dept_id: string;
  role: string;
}

interface ProjectDeptUpdate {
  role?: string;
}

// ---------------- 对话 ----------------

interface Conversation {
  id: string;
  user_id: string;
  title: string;
  agent_id?: string | null;
  project_ids: string[];
  created_at: string;
  updated_at: string;
}

interface ConversationCreate {
  title: string;
  agent_id?: string | null;
  project_ids?: string[];
}

interface ConversationUpdate {
  title?: string;
  agent_id?: string | null;
  project_ids?: string[];
}

interface ChatMessage {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
  /** 助手消息的过程区块(思考/检索等, 折叠展示) */
  blocks?: MessageBlock[] | null;
}

// RAG 聊天请求(对应后端 ChatRequest)
interface RagChatRequest {
  message: string;
  project_ids?: string[];
  deep_thinking?: boolean;
  rerank_limit?: number;
}

// 对话总结结果
interface ConversationSummary {
  title: string;
  summary: string;
}

export {
  KbCategory,
  RagRole,
  ParseStatus,
};
export type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectDocument,
  ProjectDocumentUpdate,
  SupportedFileTypes,
  ProjectMember,
  ProjectMemberCreate,
  ProjectMemberUpdate,
  MyProject,
  ProjectDept,
  ProjectDeptCreate,
  ProjectDeptUpdate,
  Conversation,
  ConversationCreate,
  ConversationUpdate,
  ChatMessage,
  RagChatRequest,
  ConversationSummary,
};

// 知识库分类显示配置
const kbCategoryOptions = [
  { label: '个人知识库', value: KbCategory.PERSONAL },
  { label: '项目知识库', value: KbCategory.PROJECT },
  { label: '公司知识库', value: KbCategory.COMPANY },
];

// 项目角色显示配置
const ragRoleOptions = [
  { label: '项目管理员', value: RagRole.PROJECT_ADMIN },
  { label: '项目编辑', value: RagRole.PROJECT_EDITOR },
  { label: '项目只读', value: RagRole.PROJECT_READER },
];

// 文档解析状态显示配置(标签类型 + 文案)
const parseStatusOptions: Record<
  string,
  { label: string; tag: 'info' | 'warning' | 'success' | 'danger' }
> = {
  [ParseStatus.PENDING]: { label: '待解析', tag: 'info' },
  [ParseStatus.PARSING]: { label: '解析中', tag: 'warning' },
  [ParseStatus.COMPLETED]: { label: '已完成', tag: 'success' },
  [ParseStatus.FAILED]: { label: '解析失败', tag: 'danger' },
};

export { kbCategoryOptions, ragRoleOptions, parseStatusOptions };
