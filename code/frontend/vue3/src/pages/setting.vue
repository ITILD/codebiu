<template>
  <div p-4 md:p-6>
    <h2 text-2xl font-bold text-note mb-6>设置</h2>

    <div class="flex flex-col md:flex-row gap-4">
      <!-- 左侧导航(移动端横向滚动, 桌面端垂直) -->
      <nav
        class="flex md:flex-col gap-1 md:w-48 shrink-0 bg-note-card rounded-lg shadow-note p-2 overflow-x-auto md:overflow-visible">
        <button v-for="tab in tabs" :key="tab.key"
          class="flex items-center gap-2 rounded px-3 py-2 text-sm whitespace-nowrap transition-colors cursor-pointer"
          :class="active === tab.key
            ? 'bg-green-600/10 text-green-700 dark:text-green-400 font-medium'
            : 'text-note-sub hover:bg-note-glass'"
          @click="active = tab.key">
          <el-icon><component :is="tab.icon" /></el-icon>
          {{ tab.label }}
        </button>
      </nav>

      <!-- 右侧内容面板 -->
      <section class="flex-1 min-w-0 bg-note-card rounded-lg shadow-note p-4 md:p-6">
        <Transition name="fade" mode="out-in">
          <component :is="activeComponent" />
        </Transition>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import { User, Lock, Brush, Key } from '@element-plus/icons-vue'
import SettingProfile from '@/app/components/setting/SettingProfile.vue'
import SettingPassword from '@/app/components/setting/SettingPassword.vue'
import SettingBase from '@/app/components/setting/SettingBase.vue'
import SettingPermission from '@/app/components/setting/SettingPermission.vue'

/** 设置分组: 个人信息(自助修改) + 系统样式 */
const tabs = [
  { key: 'profile', label: '基本信息', icon: markRaw(User), component: SettingProfile },
  { key: 'password', label: '修改密码', icon: markRaw(Lock), component: SettingPassword },
  { key: 'appearance', label: '外观设置', icon: markRaw(Brush), component: SettingBase },
  { key: 'permission', label: '我的权限', icon: markRaw(Key), component: SettingPermission },
] as const

type TabKey = (typeof tabs)[number]['key']
const active = ref<TabKey>('profile')
const activeComponent = computed(() => tabs.find((t) => t.key === active.value)?.component)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
