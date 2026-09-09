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

// 当前用户对单个知识库的操作权限位(后端 my_perms, 前端按位渲染按钮)
interface ProjectMyPerms {
  /** 可读(档位>=1) */
  read: boolean;
  /** 可上传文档(档位>=2) */
  upload_doc: boolean;
  /** 可编辑项目信息(档位>=2) */
  update: boolean;
  /** 可删除项目(档位>=3) */
  delete: boolean;
  /** 可管理成员/部门授权/发布(档位>=3) */
  manage_member: boolean;
}

interface Project {
  id: string;
  name: string;
  description?: string | null;
  is_private: boolean;
  kb_category: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  /** 当前用户操作权限位(列表/详情接口返回; 全局管理员全 true) */
  my_perms?: ProjectMyPerms | null;
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
  /** 内容SHA-256(新口径关联统一存储; 旧数据为 null) */
  content_hash?: string | null;
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
  /** 上传后自动解析任务派发警告(如所需模型未配置/队列不可用), 仅上传接口返回 */
  parse_task_warning?: string | null;
}

interface ProjectDocumentUpdate {
  name?: string;
  description?: string | null;
}

// 文档入库步骤执行状态
enum IngestStepState {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

// 单个入库步骤进度(后端流水线注册表 + 文档实际状态合并; graph/tag/web_merge 为预留步骤)
interface IngestStepProgress {
  /** 步骤编码 parse/chunk/embed/graph/tag/web_merge */
  step: string;
  name: string;
  description: string;
  /** 预留步骤为 false(灰色展示, 不计入总进度) */
  enabled: boolean;
  weight: number;
  status: IngestStepState;
  /** 步骤内完成百分比 0~100 */
  progress: number;
  message: string | null;
  error: string | null;
}

// 文档入库步骤与进度(GET /rag/project-documents/{id}/progress)
interface DocumentIngestProgress {
  document_id: string;
  parse_status: string;
  /** 总进度 0~100(按启用步骤权重加权) */
  progress: number;
  steps: IngestStepProgress[];
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
  IngestStepState,
};
export type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectMyPerms,
  ProjectDocument,
  ProjectDocumentUpdate,
  IngestStepProgress,
  DocumentIngestProgress,
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
