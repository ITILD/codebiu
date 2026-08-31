<template>
  <!-- 桌面端: 吸顶侧边栏(随页面滚动钉在导航下方, 超高时内部滚动) -->
  <el-aside
    v-if="sysSettingStore.sysStyle.isMd"
    :width="isCollapse ? '64px' : '230px'"
    transition-all
    duration-300
    class="sidebar-note"
    self-start
    sticky
    top-16
    z-10
    shrink-0
  >
    <div flex flex-col max-h-app>
      <!-- 折叠按钮(点击切换 抽屉式收窄/展开) -->
      <div flex p-2 shrink-0 :class="isCollapse ? 'justify-center' : 'justify-end'">
        <el-tooltip :content="isCollapse ? '展开菜单' : '收起菜单'" placement="right">
          <el-button
            :icon="isCollapse ? Expand : Fold"
            circle
            size="small"
            text
            bg-note-tint
            @click="isCollapse = !isCollapse"
          />
        </el-tooltip>
      </div>

      <!-- 模块菜单(超出视口高度时内部滚动) -->
      <el-scrollbar flex-1>
        <el-menu
          :default-active="routerStore.routerPath.now"
          :router="true"
          :collapse="isCollapse"
          border-0
          bg-transparent
          px-2
        >
          <template v-for="item in visibleMenuItems" :key="item.index">
            <el-menu-item v-if="!item.children" :index="item.index">
              <el-icon><component :is="item.icon" /></el-icon>
              <template #title>{{ item.title }}</template>
            </el-menu-item>

            <el-sub-menu v-else :index="item.index">
              <template #title>
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.title }}</span>
              </template>
              <el-menu-item
                v-for="child in item.children"
                :key="child.index"
                :index="child.index"
              >
                {{ child.title }}
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </el-scrollbar>

      <!-- 底部装饰小语 -->
      <div v-if="!isCollapse" px-4 py-3 text-xs text-note-sub border-t border-note shrink-0>
        🌿 记录每一份数据
      </div>
    </div>
  </el-aside>

  <!-- 移动端: 抽屉式侧边栏 -->
  <el-drawer
    v-model="sysSettingStore.sysStyle.isSidebarDrawerOpen"
    :title="TITLE"
    direction="ltr"
    size="240px"
    class="sidebar-drawer-note"
  >
    <el-menu
      :default-active="routerStore.routerPath.now"
      :router="true"
      border-0
      bg-transparent
      @select="sysSettingStore.sysStyle.isSidebarDrawerOpen = false"
    >
      <template v-for="item in visibleMenuItems" :key="item.index">
        <el-menu-item v-if="!item.children" :index="item.index">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>

        <el-sub-menu v-else :index="item.index">
          <template #title>
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </template>
          <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
            {{ child.title }}
          </el-menu-item>
        </el-sub-menu>
      </template>
    </el-menu>
  </el-drawer>
</template>

<script lang="ts" setup>
import { ref, markRaw, watch, computed } from 'vue'
import {
  HomeFilled, UserFilled, Document,
  Monitor, ChatDotRound,
  Expand, Fold, Files, Collection, FolderOpened,
  Location, Sunny,
} from '@element-plus/icons-vue'
import { RouterStore } from '@/stores/router'
import { SysSettingStore } from '@/stores/sys'
import { usePermission } from '@/composables/usePermission'

const routerStore = RouterStore()
const sysSettingStore = SysSettingStore()
const TITLE = import.meta.env.VITE_GLOB_APP_TITLE
const { hasPerm } = usePermission()

const isCollapse = ref(false)

/** 菜单项定义(perm 为权限码:与后端模块权限声明一致;缺省表示登录即可见) */
interface MenuItem {
  index: string
  icon?: ReturnType<typeof markRaw>
  title: string
  perm?: string
  children?: { index: string; title: string; perm?: string }[]
}

// 全局模块菜单(RuoYi式: 首页+按后端模块分组, 账户设置在头像下拉)
// 分组与后端 module_* 一一对应: authorization/rag/ai/file/geometry/main,
// 生活工具组跨 module_life + module_little_utils 两个后端模块
const menuItems: MenuItem[] = [
  {
    index: '/',
    icon: markRaw(HomeFilled),
    title: '首页',
  },
  {
    index: '/_sys',
    icon: markRaw(Monitor),
    title: '系统概览',
  },
  {
    index: '/_sys/manager',
    icon: markRaw(UserFilled),
    title: '权限管理',
    perm: 'sys',
    children: [
      { index: '/_sys/manager/user', title: '用户管理', perm: 'sys:user' },
      { index: '/_sys/manager/role', title: '角色管理', perm: 'sys:role' },
      { index: '/_sys/manager/dept', title: '部门管理', perm: 'sys:dept' },
      { index: '/_sys/manager/permission', title: '权限管理', perm: 'sys:permission' },
      { index: '/_sys/manager/casbin', title: '策略规则', perm: 'sys:casbin' },
    ],
  },
  {
    index: '/_sys/rag',
    icon: markRaw(Collection),
    title: '知识库',
    perm: 'rag',
    children: [
      { index: '/_sys/rag/project', title: '知识库管理', perm: 'rag:project' },
      { index: '/_sys/rag/document', title: '文档管理', perm: 'rag:doc' },
      { index: '/_sys/rag/member', title: '成员管理', perm: 'rag:member' },
      { index: '/_sys/rag/conversation', title: '知识库问答', perm: 'rag:chat' },
    ],
  },
  {
    index: '/_sys/ai',
    icon: markRaw(ChatDotRound),
    title: 'AI 服务',
    children: [
      { index: '/_sys/ai/chat', title: 'AI 对话' },
      { index: '/_sys/ai/model_config', title: '模型配置' },
      { index: '/_sys/ai/ocr', title: 'OCR 识别' },
      { index: '/_sys/ai/voice', title: '语音识别' },
    ],
  },
  {
    index: '/_sys/file',
    icon: markRaw(FolderOpened),
    title: '文件管理',
    perm: 'main:file',
  },
  {
    index: '/_sys/geometry',
    icon: markRaw(Location),
    title: '地理空间',
    perm: 'geometry',
    children: [
      { index: '/_sys/geometry/earth', title: '地球绘制', perm: 'geometry:feature' },
    ],
  },
  {
    index: '/_sys/life',
    icon: markRaw(Sunny),
    title: '生活工具',
    children: [
      { index: '/_sys/life/baby_name', title: '宝宝取名' },
      { index: '/_sys/little_utils/todolist', title: '待办事项' },
    ],
  },
  {
    index: '/_sys/database',
    icon: markRaw(Document),
    title: '数据管理',
    children: [
      { index: '/_sys/database/overview', title: '数据概览', perm: 'main:db' },
      { index: '/_sys/database/user', title: '用户数据', perm: 'main:db' },
      { index: '/_sys/database/dict', title: '字段表管理', perm: 'main:dict' },
    ],
  },
  {
    index: '/_sys/monitor',
    icon: markRaw(Monitor),
    title: '系统监控',
    children: [
      { index: '/_sys/monitor/uistore', title: '状态查看' },
      { index: '/_sys/monitor/server_status', title: '服务状态' },
    ],
  },
  {
    index: '/_sys/template',
    icon: markRaw(Files),
    title: '模板示例',
    children: [
      { index: '/_sys/template/overview', title: '模板概览' },
      { index: '/_sys/template/template', title: '模板管理' },
      { index: '/_sys/template/container', title: '布局容器' },
      { index: '/_sys/template/mediapipe_face', title: '人脸识别' },
      { index: '/_sys/template/babylon', title: 'Babylon 3D' },
    ],
  },
]

/** 按权限码过滤后的可见菜单(未声明 perm 的项登录即可见) */
const visibleMenuItems = computed<MenuItem[]>(() => {
  return menuItems
    .map((item) => {
      // 目录自身声明了权限码: 无权限直接隐藏整组
      if (item.perm && !hasPerm(item.perm)) return null
      // 子菜单逐项过滤(声明了 perm 的子项需有权限)
      if (item.children) {
        const children = item.children.filter((c) => !c.perm || hasPerm(c.perm))
        if (children.length === 0) return null
        return { ...item, children }
      }
      return item
    })
    .filter((item): item is MenuItem => item !== null)
})

// 桌面端时关闭移动抽屉
watch(
  () => sysSettingStore.sysStyle.isMd,
  (isMd) => {
    if (isMd) sysSettingStore.sysStyle.isSidebarDrawerOpen = false
  }
)
</script>

<style scoped>
/* 侧边栏: 淡绿纸底 + 右侧装订虚线 */
.sidebar-note {
  background-color: var(--note-soft);
  border-right: 1px solid var(--note-border);
  /* 内侧装订虚线(笔记本感) */
  box-shadow: inset -6px 0 0 -5px rgba(107, 158, 120, 0.18);
}
</style>
