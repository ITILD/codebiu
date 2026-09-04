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
import { ref, watch } from 'vue'
import { Expand, Fold } from '@element-plus/icons-vue'
import { RouterStore } from '@/common/stores/router'
import { SysSettingStore } from '@/common/stores/sys'
import { useVisibleMenu } from '@/common/composables/useMenu'

const routerStore = RouterStore()
const sysSettingStore = SysSettingStore()
const TITLE = import.meta.env.VITE_GLOB_APP_TITLE
// 菜单数据与权限过滤统一来自共享层(common/config/menu.ts + useMenu)
const { visibleMenuItems } = useVisibleMenu()

// 三档响应式折叠: 手机(<768)抽屉 / 平板(768-1023)默认折叠图标栏 / 桌面(>=1024)默认展开
const isCollapse = ref(!sysSettingStore.sysStyle.isLg)
// 跨断点(旋转/拉伸窗口)时重置为该档默认值
watch(
  () => sysSettingStore.sysStyle.isLg,
  (v) => {
    isCollapse.value = !v
  }
)

// 升到平板及以上时关闭移动抽屉(已由常驻侧边栏接管)
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
