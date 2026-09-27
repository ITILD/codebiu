/**
 * 版本信息数据源
 *
 * 与 doc/doc_ch/06-版本开发 逐版本记录保持一致（含 0.x 初始开发期）。
 * 版本规则：每月至少一个版本；大的功能改动增补中间小版本；相邻版本发布间隔不少于一周。
 * 数组按"最新在前"排序，版本页时间线配合无限滚动分批渲染，避免一次性挂载全部条目。
 */

/** 单条版本功能 */
export interface VersionFeature {
  /** 功能名称 */
  title: string
  /** 功能说明 */
  desc: string
}

/** 版本记录 */
export interface VersionRecord {
  /** 版本号 */
  version: string
  /** 版本主题名 */
  name: string
  /** 开发周期（展示用） */
  period: string
  /** 状态：released 已发布 / dev 开发中 */
  status: 'released' | 'dev'
  /** 一句话简介 */
  summary: string
  /** 亮点标签 */
  tags: string[]
  /** 功能明细 */
  features: VersionFeature[]
}

/** 项目介绍（版本页 Hero 区） */
export const projectIntro = {
  /** 项目名 */
  name: 'Codebiu',
  /** 标语 */
  tagline: '多平台快速开发部署基线项目',
  /** 项目简介 */
  description:
    '前后端分离 + 文档 + 运维一体化的项目模板：FastAPI + Vue3 基线开箱即用，' +
    '认证、权限、文件、数据库、AI 能力即插即用，新项目复制即起步。' +
    '自 2025-11 设立起按月迭代，逐版本记录见开发文档。',
} as const

/** 主要功能列表（版本页 Hero 下方功能卡片） */
export const mainFeatures = [
  {
    icon: 'Lock',
    title: '权限体系',
    desc: 'Casbin 域分离 RBAC（菜单 / 按钮 / 接口）+ 项目级数据权限（成员 / 部门三档位）',
  },
  {
    icon: 'MagicStick',
    title: 'AI 能力',
    desc: 'LLM 流式对话、OCR、重排、语音 ASR/TTS、RAG 知识库、智能体、LLM 数据清洗',
  },
  {
    icon: 'Files',
    title: '通用底座',
    desc: 'JWT 认证、文件系统（预签名 URL / 去重 / 引用计数）、多数据库、双引擎任务调度',
  },
  {
    icon: 'Search',
    title: '网页搜索',
    desc: 'Tavily / Firecrawl 搜索引擎集成，联网检索即取即用',
  },
  {
    icon: 'Compass',
    title: '前台应用',
    desc: '个人小站、RAG 对话、三维地理可视化、街机小游戏等开箱应用',
  },
  {
    icon: 'SetUp',
    title: '工程化',
    desc: 'uv / pnpm 包管理、docker 开发部署、SQLite + Fakeredis + LanceDB 零依赖本地开发',
  },
] as const

/** 版本记录（最新在前） */
export const versions: VersionRecord[] = [
  {
    version: 'v1.4.0',
    name: '动态配置中心版',
    period: '2026-09-18 ~ 至今',
    status: 'dev',
    summary: '配置从 yaml 走向数据库动态化管理，管理员页面改配置即时生效。',
    tags: ['配置中心', '权限', '体验'],
    features: [
      { title: '动态配置中心', desc: 'sys_config 表 + 分组 schema + TTL 缓存，token / 邮件 / 搜索 / 存储等九组配置动态化' },
      { title: '恒定门面装配', desc: 'db.py 重构为"恒定门面代理 + 显式装配"，存量用法零改动支持配置热刷新' },
      { title: '通用配置页', desc: '元数据驱动表单、密钥打码、连接级配置"重启生效"标注' },
      { title: '悬浮工具', desc: '可拖动悬浮工具组件与独立下载权限体系' },
    ],
  },
  {
    version: 'v1.3.0',
    name: '任务引擎与体验统一版',
    period: '2026-09-09 ~ 09-17',
    status: 'released',
    summary: '任务调度双引擎化，AI 工具链全量重构，全站 UI 风格统一。',
    tags: ['任务调度', 'AI', 'UI'],
    features: [
      { title: '双引擎任务调度', desc: '新增本地任务执行引擎，与 Celery 形成双引擎调度' },
      { title: '大模型工具链全量重构', desc: 'module_ai 新增 OCR、LLM 工具链与重排，模型自动检测与缓存' },
      { title: '语音与会话标题', desc: '模型设置面板重构，新增语音模型支持，会话标题自动生成' },
      { title: '体验统一', desc: '统一 UI 风格、聊天布局与文案优化、个人小站路由重构' },
    ],
  },
  {
    version: 'v1.2.0',
    name: '智能扩展版',
    period: '2026-09-01 ~ 09-08',
    status: 'released',
    summary: '智能体、数据清洗、地理可视化集中上线，权限与模型管理升级。',
    tags: ['智能体', 'RAG', 'GIS', '权限'],
    features: [
      { title: '智能体模块', desc: 'agent 模块上线，工作流与对话页面布局交互完善' },
      { title: 'LLM 数据清洗', desc: '独立数据清洗模块，复用 AI 模块的 LLM 服务' },
      { title: '三维地理可视化', desc: 'GIS 模块上线，完善认证与监控功能' },
      { title: '模型分部门管理', desc: 'AI 模型按 public / dept / user 三类 scope 隔离' },
      { title: 'OAuth2 登录', desc: '标准登录端点，支持 Swagger Authorize' },
      { title: 'RAG 优化', desc: '知识库页面结构重构、rerank 重构与向量库流程优化' },
    ],
  },
  {
    version: 'v1.1.0',
    name: '工程化版本',
    period: '2026-08',
    status: 'released',
    summary: '模型工具链统一，容器化部署链路补全。',
    tags: ['工具链', '容器化'],
    features: [
      { title: 'LLM 工具链重构', desc: '重构 AI 模型加载工具链，形成统一加载入口' },
      { title: '模型增强', desc: 'Qwen 推理内容提取、huggingface-hub 模型下载脚本' },
      { title: '容器化与运维', desc: 'deveops 运维脚本、前端 docker 构建配置' },
    ],
  },
  {
    version: 'v1.0.0',
    name: '基线稳定版',
    period: '2026-07',
    status: 'released',
    summary: '项目进入稳定期，RAG、权限、语音三大能力落地。',
    tags: ['RAG', '权限', '语音'],
    features: [
      { title: 'RAG 知识库', desc: '知识库管理、文档解析与检索问答链路' },
      { title: '权限系统重构', desc: 'Casbin RBAC 域分离模型，按模块声明权限' },
      { title: '语音模块', desc: '完整的 ASR / TTS 语音识别与合成' },
      { title: '工程治理', desc: 'StrEnum 全面替换、全局 app name / version 配置' },
    ],
  },
  {
    version: 'v0.7.0',
    name: '场景扩展版',
    period: '2026-05',
    status: 'released',
    summary: 'MCP 协议打通，业务场景扩展。',
    tags: ['MCP', '业务'],
    features: [
      { title: 'MCP 集成', desc: 'fastmcp 接入，FastAPI 与 MCP 协议打通' },
      { title: '宝宝名字预测', desc: 'baby_name 业务功能模块' },
    ],
  },
  {
    version: 'v0.6.0',
    name: '工具与三维版',
    period: '2026-04',
    status: 'released',
    summary: 'LLM 具备工具调用能力，三维渲染起步。',
    tags: ['工具调用', '3D'],
    features: [
      { title: 'llm_tools 模块', desc: 'prompt 设计与外部工具调用' },
      { title: '3D 可视化', desc: 'Babylon.js 三维渲染 + MediaPipe 面部检测' },
    ],
  },
  {
    version: 'v0.5.0',
    name: '流式聊天版',
    period: '2026-03',
    status: 'released',
    summary: '流式聊天跑通，NLP 同义词模块上线。',
    tags: ['SSE', 'NLP'],
    features: [
      { title: 'SSE 流式响应', desc: 'LLM 事件流式输出，聊天消息实时渲染' },
      { title: '同义词管理', desc: '批量分组查询与批量更新' },
      { title: '图数据库迁移', desc: 'kuzu → ladybug 引擎迁移' },
    ],
  },
  {
    version: 'v0.4.0',
    name: '文件系统完善版',
    period: '2026-02',
    status: 'released',
    summary: '文件系统收尾：去重、引用计数与测试基建。',
    tags: ['文件系统'],
    features: [
      { title: '文件内容去重', desc: '基于 content_hash 去重，相同内容只存一份' },
      { title: '引用计数', desc: '文件条目引用计数，预签名上传闭环' },
    ],
  },
  {
    version: 'v0.3.0',
    name: '文件存储重构版',
    period: '2026-01',
    status: 'released',
    summary: '文件存储多端兼容，认证与监控成型。',
    tags: ['文件存储', '认证', '监控'],
    features: [
      { title: '多存储与预签名 URL', desc: '本地 / S3 对象存储兼容，预签名上传下载' },
      { title: 'AI 模块启用', desc: 'AI 模块正式启用，LLM 请求基础模板' },
      { title: '认证体系重构', desc: 'auth store、token 时区支持、用户下拉菜单' },
      { title: '系统监控', desc: '状态监控页与 Monaco 代码编辑器、字典管理模块' },
    ],
  },
  {
    version: 'v0.2.0',
    name: '多数据库版',
    period: '2025-12',
    status: 'released',
    summary: '关系 / 向量 / 图多数据库格局成型。',
    tags: ['数据库', 'AI 模型'],
    features: [
      { title: '向量数据库', desc: 'Milvus Lite → LanceDB，统一接口与基类抽象' },
      { title: '图数据库', desc: 'Neo4j 支持与单步关联查询' },
      { title: '模型接入', desc: 'Ollama / AWS 模型支持，模型配置校验增强' },
      { title: '任务队列', desc: 'Celery + Redis 任务队列引入' },
    ],
  },
  {
    version: 'v0.1.0',
    name: '基线初始化版',
    period: '2025-11-14 ~ 11-30',
    status: 'released',
    summary: '项目从零起步，前后端基线与开发闭环跑通。',
    tags: ['基线', '起点'],
    features: [
      { title: '前后端基线', desc: 'FastAPI + uv 后端结构、Vue3 / React 前端框架' },
      { title: '认证雏形', desc: '登录注册流程初步接入' },
      { title: '模块探索', desc: 'OCR 前后端、Excel 处理、模板管理、常用图标' },
      { title: '打包方案', desc: 'Nuitka 加密编译打包验证' },
    ],
  },
]
