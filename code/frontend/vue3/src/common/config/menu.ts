/**
 * 全局菜单配置(RuoYi 式目录)
 * 共用方: SysSidebar(后台侧边栏) / SysBreadcrumb(面包屑) / 主页主应用入口卡 / 头像下拉
 * 菜单分两类:
 * - 主应用(mainApp: true): 个人小站/知识库/地球绘制, 从首页直接进入, 无侧边栏,
 *   模块内孙页面导航由各模块页面自行承担
 * - 后台管理(其余): 仅经头像下拉"后台管理"入口进入, 显示侧边栏
 * 分组与后端 module_* 一一对应: authorization/rag/ai/file/geometry/site/main,
 * 生活工具组对应 module_life
 */
import { markRaw } from 'vue'
import type { Component } from 'vue'
import {
  HomeFilled, UserFilled, Document,
  Monitor, ChatDotRound,
  Files, Collection, FolderOpened,
  Location, Sunny, Timer, Brush, Connection, Notebook, MagicStick,
} from '@element-plus/icons-vue'

/** 菜单项定义(perm 为权限码:与后端模块权限声明一致;缺省表示登录即可见) */
export interface MenuItem {
  /** 路由路径(与 el-menu index 一致) */
  index: string
  icon?: Component
  title: string
  /** 权限码(缺省登录即可见) */
  perm?: string
  /** 主页模块入口卡的描述文案(菜单不渲染) */
  desc?: string
  /** 主应用标记: 从首页直接进入的前台应用, 不进后台侧边栏 */
  mainApp?: boolean
  children?: { index: string; title: string; perm?: string }[]
}

export const menuItems: MenuItem[] = [
  {
    index: '/',
    icon: markRaw(HomeFilled),
    title: '首页',
  },
  {
    index: '/admin',
    icon: markRaw(Monitor),
    title: '系统概览',
    desc: '系统运行状态、快捷入口与最近访问。',
  },
  {
    index: '/authorization',
    icon: markRaw(UserFilled),
    title: '权限管理',
    perm: 'sys',
    desc: '用户、角色、部门与权限策略管理。',
    children: [
      { index: '/authorization/user', title: '用户管理', perm: 'sys:user' },
      { index: '/authorization/role', title: '角色管理', perm: 'sys:role' },
      { index: '/authorization/dept', title: '部门管理', perm: 'sys:dept' },
      { index: '/authorization/permission', title: '权限管理', perm: 'sys:permission' },
      { index: '/authorization/casbin', title: '策略规则', perm: 'sys:casbin' },
    ],
  },
  {
    index: '/rag',
    icon: markRaw(Collection),
    title: '知识库',
    perm: 'rag',
    mainApp: true,
    desc: '项目、文档、成员与问答,一处管理。',
    children: [
      // 首页入口卡取 children[0] 跳转, 问答页为主入口(管理入口在问答页侧栏)
      { index: '/rag/conversation', title: '知识库问答', perm: 'rag:chat' },
      { index: '/rag/project', title: '知识库管理', perm: 'rag:project' },
    ],
  },
  {
    index: '/agent',
    icon: markRaw(MagicStick),
    title: '智能体',
    perm: 'agent',
    mainApp: true,
    desc: '内置翻译/写作/代码智能体, 支持自定义简单智能体。',
    children: [
      { index: '/agent/chat', title: '智能体对话', perm: 'agent:chat' },
      { index: '/agent/manage', title: '智能体管理', perm: 'agent:manage' },
    ],
  },
  {
    index: '/ai',
    icon: markRaw(ChatDotRound),
    title: 'AI 服务',
    desc: 'AI 对话、模型配置、OCR 识别与语音能力。',
    children: [
      { index: '/ai/chat', title: 'AI 对话' },
      { index: '/ai/model_config', title: '模型配置' },
      { index: '/ai/ocr', title: 'OCR 识别' },
      { index: '/ai/voice', title: '语音识别' },
    ],
  },
  {
    index: '/data_clean',
    icon: markRaw(Brush),
    title: '数据清洗',
    desc: 'LLM 驱动的数据清洗与结构化转换。',
  },
  {
    index: '/file',
    icon: markRaw(FolderOpened),
    title: '文件管理',
    perm: 'main:file',
    desc: '虚拟文件系统,目录式浏览与秒传。',
  },
  {
    index: '/geometry',
    icon: markRaw(Location),
    title: '地球绘制',
    perm: 'geometry',
    mainApp: true,
    desc: '卡通风格地球绘制与三维要素编辑。',
    children: [
      { index: '/geometry/earth', title: '地球绘制', perm: 'geometry:feature' },
    ],
  },
  {
    index: '/task',
    icon: markRaw(Timer),
    title: '任务队列',
    perm: 'task',
    desc: '异步任务提交、进度与重试管理。',
    children: [
      { index: '/task/queue', title: '任务列表', perm: 'task:queue' },
    ],
  },
  {
    index: '/site',
    icon: markRaw(Notebook),
    title: '个人小站',
    perm: 'site',
    mainApp: true,
    desc: '博客、备忘与记账的一站式工作台。',
    children: [
      { index: '/site', title: '工作台', perm: 'site' },
      { index: '/site/blog_view', title: '博客展示', perm: 'site:blog' },
    ],
  },
  {
    index: '/life',
    icon: markRaw(Sunny),
    title: '生活工具',
    desc: '宝宝取名等轻量生活工具。',
    children: [
      { index: '/life/baby_name', title: '宝宝取名' },
    ],
  },
  {
    index: '/main',
    icon: markRaw(Document),
    title: '数据管理',
    desc: '数据概览与字段表管理。',
    children: [
      { index: '/main/overview', title: '数据概览', perm: 'main:db' },
      { index: '/main/dict', title: '字段表管理', perm: 'main:dict' },
    ],
  },
  {
    index: '/monitor',
    icon: markRaw(Monitor),
    title: '系统监控',
    desc: '前端状态与服务器硬件状态查看。',
    children: [
      { index: '/monitor/uistore', title: '状态查看' },
      { index: '/monitor/server_status', title: '服务状态' },
    ],
  },
  {
    index: '/api_test',
    icon: markRaw(Connection),
    title: '接口测试',
    desc: '前端全部接口连通性测试与结果查看。',
  },
  {
    index: '/template',
    icon: markRaw(Files),
    title: '模板示例',
    desc: '布局容器、3D 场景等前端范例。',
    children: [
      { index: '/template/overview', title: '模板概览' },
      { index: '/template/playground', title: '组件选型' },
      { index: '/template/template', title: '模板管理' },
      { index: '/template/container', title: '布局容器' },
      { index: '/template/mediapipe_face', title: '人脸识别' },
      { index: '/template/babylon', title: 'Babylon 3D' },
    ],
  },
]

/** 后台管理菜单(供侧边栏/头像下拉使用): 全量树剔除主应用分组 */
export const adminMenuItems: MenuItem[] = menuItems.filter((item) => !item.mainApp)

/** 主应用入口(供首页入口卡使用): 保持配置顺序展示 */
export const mainApps: MenuItem[] = menuItems.filter((item) => item.mainApp)

/**
 * 按路由路径精确匹配菜单树,返回面包屑轨迹 ['首页','分组','当前页']
 * - '/' 返回 [首页]; 无匹配(如 /setting)返回 [] → 面包屑不渲染
 * - 路径以分组 index 开头但无子项精确匹配时,返回 [分组](分组本身作为当前页)
 */
export function findMenuTrail(path: string): MenuItem[] {
  // 首页特殊处理
  if (path === '/') return [menuItems[0]]
  // 依次检查每个分组
  for (const group of menuItems) {
    if (group.index === '/') continue
    // 精确命中分组(无子项的直接入口,如 /file)
    if (group.index === path) return [menuItems[0], group]
    // 在子项中精确匹配
    const child = group.children?.find((c) => c.index === path)
    if (child) {
      // 构造携带标题的子项节点(面包屑只需 title)
      return [menuItems[0], group, { ...group, ...child, children: undefined, icon: undefined }]
    }
  }
  // 未收录的路径(如账户设置)不显示面包屑
  return []
}
