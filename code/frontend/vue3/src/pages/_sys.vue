<template>
  <!-- sys 页-->
  <!-- 内容 -->
  <div flex w-full>
    <!-- 左侧菜单 -->
    <el-menu
      h-full
      :default-active="routerStore.routerPath.now"
      :router="true"
      overflow-y-auto
      :collapse="isCollapse"
      :w="!isCollapse ? '60' : ''"
      @select="handleSelect"
    >
      <!-- Logo 区域（折叠时隐藏文字） -->
      <div flex items-center justify-between p-3 border-b h-12>
        <div flex items-center transition-all duration-300 ease-in-out>
          <transition name="fade" mode="out-in">
            <span v-if="!isCollapse" pl-4 text-xl font-bold whitespace-nowrap>Sys State</span>
          </transition>
        </div>
        <el-button
          transition-all
          duration-300
          hover:scale-110
          @click="isCollapse = !isCollapse"
          :icon="isCollapse ? DArrowRight : DArrowLeft"
          plain
        />
      </div>
      <!-- 菜单项 -->
      <template v-for="item in menuItems" :key="item.index">
        <el-menu-item v-if="!item.children" :index="item.index" :disabled="item.disabled">
          <el-icon v-if="item.icon">
            <component :is="item.icon" />
          </el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>

        <el-sub-menu v-else :index="item.index">
          <template #title>
            <el-icon v-if="item.icon">
              <component :is="item.icon" />
            </el-icon>
            <span>{{ item.title }}</span>
          </template>

          <!-- 子菜单项 -->
          <template v-for="child in item.children" :key="child.index">
            <el-menu-item v-if="!child.children" :index="child.index" :disabled="child.disabled">
              {{ child.title }}
            </el-menu-item>
            <el-sub-menu v-else :index="child.index">
              <!-- 子子菜单 -->
              <template #title>{{ child.title }}</template>
              <el-menu-item
                v-for="grandChild in child.children"
                :key="(grandChild as any).index"
                :index="(grandChild as any).index"
                :disabled="(grandChild as any).disabled"
              >
                {{ (grandChild as any).title }}
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-sub-menu>
      </template>
    </el-menu>
    <!-- 右侧菜单 -->
    <div flex-1 min-w-0 overflow-auto>
      <!-- flex剩余 -->
      <router-view w-full h-full></router-view>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, markRaw } from 'vue'
import { Document, Menu, Location, Setting, DArrowRight, DArrowLeft } from '@element-plus/icons-vue'
import { RouterStore } from '@/stores/router'

// 初始化路由存储
const routerStore = RouterStore()

// 菜单折叠状态
const isCollapse = ref(true)

// 菜单项配置
const menuItems = ref([
  {
    index: '/_sys',
    icon: markRaw(Location),
    title: 'Overview',
    disabled: false,
    children: null,
  },
  {
    index: '/authorization',
    title: 'Authorization',
    icon: markRaw(Setting),
    disabled: false,
    children: [
      {
        index: '/_sys/authorization/user',
        title: 'user',
        disabled: false,
        children: null,
      },
    ],
  },
  {
    index: '/_sys/monitor',
    title: 'Monitor',
    icon: markRaw(Setting),
    disabled: false,
    children: [
      {
        index: '/_sys/monitor/overview',
        title: 'overview',
        disabled: false,
        children: null,
      },
      {
        index: '/_sys/monitor/uistore',
        title: 'uistore',
        disabled: false,
        children: null,
      },
    ],
  },
  {
    index: '/db',
    title: 'DataBase',
    icon: markRaw(Setting),
    children: [
      {
        index: '/_sys/database/overview',
        title: 'overview',
        disabled: false,
        children: null,
      },
      {
        index: '/_sys/database/model_config',
        title: 'model_config',
        disabled: false,
        children: null,
      },
    ],
  },
  {
    index: '/template',
    title: 'Template',
    icon: markRaw(Setting),
    children: [
      {
        index: '/_sys/template/overview',
        title: 'overview',
        disabled: false,
        children: null,
      },
      {
        index: '/_sys/template/template',
        title: 'template',
        disabled: false,
        children: null,
      },
      {
        index: '/_sys/template/container',
        title: 'container布局',
        disabled: false,
        children: null,
      },
    ],
  },
  {
    index: '/ai',
    title: 'AI',
    icon: markRaw(Setting),
    children: [
      {
        index: '/_sys/ai/ocr',
        title: 'ocr',
        disabled: false,
        children: null,
      },
      {
        index: '/_sys/ai/chat',
        title: 'chat',
        disabled: false,
        children: null,
      },
    ],
  },
  {
    index: '/_sys/test',
    title: 'test',
    icon: markRaw(Menu),
    disabled: false,
    children: null,
  },
  {
    index: '4',
    title: 'no_page',
    icon: markRaw(Document),
    disabled: false,
    children: null,
  },
  {
    index: '5',
    title: 'disabled',
    icon: markRaw(Document),
    disabled: true,
    children: null,
  },
])

// 菜单选择处理
const handleSelect = (index: string) => {
  console.log('选中菜单:', index)
}
</script>

<style scoped>
/* 使用CSS类替代属性选择器以确保兼容性 */
:deep(.el-menu) {
  height: 100%;
}
</style>
