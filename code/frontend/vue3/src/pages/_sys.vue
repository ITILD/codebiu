<template>
  <div flex w-full h-full>
    <!-- 桌面端侧边栏 -->
    <el-aside v-if="sysSettingStore.sysStyle.isMd" :width="isCollapse ? '64px' : '220px'" transition-all duration-300 border-r bg-deep-1>
      <div flex flex-col h-full>
        <!-- Logo -->
        <div flex items-center h-14 border-b shrink-0 :class="isCollapse ? 'justify-center' : 'px-4'">
          <img src="@/assets/img/ion/sy_w.svg" h-6 />
          <span v-if="!isCollapse" ml-2 text-lg font-bold whitespace-nowrap>管理后台</span>
        </div>

        <!-- 折叠按钮 -->
        <div flex :class="isCollapse ? 'justify-center' : 'justify-end'" p-2 shrink-0>
          <el-button :icon="isCollapse ? Expand : Fold" circle size="small" @click="isCollapse = !isCollapse" />
        </div>

        <!-- 菜单 -->
        <el-menu flex-1 :default-active="routerStore.routerPath.now" :router="true" :collapse="isCollapse"
          overflow-y-auto border-0 bg-transparent>
          <template v-for="item in menuItems" :key="item.index">
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
      </div>
    </el-aside>

    <!-- 移动端抽屉 -->
    <el-drawer v-model="mobileDrawer" title="管理后台" direction="ltr" size="260px">
      <el-menu :default-active="routerStore.routerPath.now" :router="true" @select="mobileDrawer = false">
        <template v-for="item in menuItems" :key="item.index">
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

    <!-- 主内容区 -->
    <div flex-1 min-w-0 flex flex-col overflow-hidden>
      <!-- 移动端顶部栏 -->
      <div v-if="!sysSettingStore.sysStyle.isMd" flex items-center gap-3 h-12 px-3 border-b bg-deep-1 shrink-0>
        <el-button :icon="Expand" circle size="small" @click="mobileDrawer = true" />
        <span text-sm font-semibold>管理后台</span>
      </div>

      <!-- 路由内容 -->
      <div flex-1 overflow-auto>
        <router-view w-full h-full />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, markRaw, watch } from 'vue'
import {
  HomeFilled, UserFilled, Document,
  Monitor, ChatDotRound, Setting,
  Expand, Fold, Files
} from '@element-plus/icons-vue'
import { RouterStore } from '@/stores/router'
import { SysSettingStore } from '@/stores/sys'

const routerStore = RouterStore()
const sysSettingStore = SysSettingStore()

const isCollapse = ref(false)
const mobileDrawer = ref(false)

// 菜单项配置
const menuItems = [
  {
    index: '/_sys',
    icon: markRaw(HomeFilled),
    title: '系统概览',
  },
  {
    index: '/_sys/manager',
    icon: markRaw(UserFilled),
    title: '管理员',
    children: [
      { index: '/_sys/manager/user', title: '用户管理' },
      { index: '/_sys/manager/role', title: '角色管理' },
      { index: '/_sys/manager/dept', title: '部门管理' },
      { index: '/_sys/manager/permission', title: '权限管理' },
    ],
  },
  {
    index: '/_sys/database',
    icon: markRaw(Document),
    title: '数据库',
    children: [
      { index: '/_sys/database/overview', title: '数据概览' },
      { index: '/_sys/database/user', title: '用户数据' },
      { index: '/_sys/database/model_config', title: '模型配置' },
      { index: '/_sys/database/todolist', title: '待办事项' },
    ],
  },
  {
    index: '/_sys/ai',
    icon: markRaw(ChatDotRound),
    title: 'AI 功能',
    children: [
      { index: '/_sys/ai/chat', title: 'AI 对话' },
      { index: '/_sys/ai/ocr', title: 'OCR 识别' },
      { index: '/_sys/ai/agent_baby_name', title: '宝宝取名' },
    ],
  },
  {
    index: '/_sys/monitor',
    icon: markRaw(Monitor),
    title: '监控',
    children: [
      { index: '/_sys/monitor/uistore', title: '状态查看' },
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
  {
    index: '/_sys/setting',
    icon: markRaw(Setting),
    title: '系统设置',
  },
]

// 桌面端时关闭移动抽屉
watch(() => sysSettingStore.sysStyle.isMd, (isMd) => {
  if (isMd) mobileDrawer.value = false
})
</script>
