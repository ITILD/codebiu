<template>
  <div p-4 md:p-6>
    <!-- 欢迎区域 -->
    <div mb-6 flex items-center justify-between flex-wrap gap-4>
      <div>
        <h2 text-2xl font-bold text-gray-800 dark:text-gray-200>系统概览</h2>
        <p text-sm text-gray-500 mt-1>欢迎使用后台管理系统</p>
      </div>
      <el-button type="primary" :icon="Refresh" @click="refreshData">刷新数据</el-button>
    </div>

    <!-- 统计卡片 -->
    <div grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6>
      <el-card v-for="stat in stats" :key="stat.label" shadow="hover" class="stat-card">
        <div flex items-center justify-between>
          <div>
            <p text-sm text-gray-500>{{ stat.label }}</p>
            <p text-2xl font-bold mt-2 :class="stat.color">{{ stat.value }}</p>
          </div>
          <el-icon :size="36" :class="stat.color" opacity-60>
            <component :is="stat.icon" />
          </el-icon>
        </div>
      </el-card>
    </div>

    <!-- 快捷入口 -->
    <div mb-6>
      <h3 text-lg font-semibold text-gray-700 dark:text-gray-300 mb-4>快捷入口</h3>
      <div grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3>
        <RouterLink
          v-for="shortcut in shortcuts"
          :key="shortcut.path"
          :to="shortcut.path"
          flex flex-col items-center p-4 rounded-lg bg-gray-50 dark:bg-gray-800
          transition-all duration-300 hover:-translate-y-1 hover:shadow-md
        >
          <el-icon :size="28" mb-2 :class="shortcut.color">
            <component :is="shortcut.icon" />
          </el-icon>
          <span text-sm text-gray-600 dark:text-gray-400>{{ shortcut.label }}</span>
        </RouterLink>
      </div>
    </div>

    <!-- 系统信息 -->
    <div grid grid-cols-1 lg:grid-cols-2 gap-4>
      <el-card shadow="never">
        <template #header>
          <span font-semibold>系统信息</span>
        </template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统版本">v1.0.0</el-descriptions-item>
          <el-descriptions-item label="运行环境">{{ sysInfo.env }}</el-descriptions-item>
          <el-descriptions-item label="主题模式">{{ sysSettingStore.sysStyle.theme.isDark ? '深色' : '浅色' }}</el-descriptions-item>
          <el-descriptions-item label="当前语言">{{ sysSettingStore.sysStyle.language === 'zh' ? '中文' : 'English' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <span font-semibold>最近访问</span>
        </template>
        <div space-y-2>
          <div
            v-for="item in recentPages"
            :key="item.path"
            flex items-center justify-between p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800
            cursor-pointer
            @click="router.push(item.path)"
          >
            <div flex items-center gap-2>
              <el-icon text-gray-400><component :is="item.icon" /></el-icon>
              <span text-sm>{{ item.label }}</span>
            </div>
            <el-icon text-gray-300><ArrowRight /></el-icon>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import {
  Refresh, User, Avatar, UserFilled, DataAnalysis,
  ChatDotRound, DocumentCopy, Monitor, Setting,
  ArrowRight, FolderOpened, Cpu
} from '@element-plus/icons-vue'
import { SysSettingStore } from '@/stores/sys'

const router = useRouter()
const sysSettingStore = SysSettingStore()

const sysInfo = {
  env: import.meta.env.MODE === 'development' ? '开发环境' : '生产环境',
}

const stats = ref([
  { label: '用户总数', value: '-', color: 'text-blue-500', icon: markRaw(User) },
  { label: '角色数量', value: '-', color: 'text-green-500', icon: markRaw(Avatar) },
  { label: '数据表', value: '-', color: 'text-orange-500', icon: markRaw(DataAnalysis) },
  { label: 'API请求', value: '-', color: 'text-purple-500', icon: markRaw(Cpu) },
])

const shortcuts = [
  { path: '/_sys/manager/user', label: '用户管理', icon: markRaw(User), color: 'text-blue-500' },
  { path: '/_sys/manager/role', label: '角色管理', icon: markRaw(UserFilled), color: 'text-green-500' },
  { path: '/_sys/database/todolist', label: '待办事项', icon: markRaw(DocumentCopy), color: 'text-orange-500' },
  { path: '/_sys/ai/chat', label: 'AI 对话', icon: markRaw(ChatDotRound), color: 'text-purple-500' },
  { path: '/_sys/monitor/uistore', label: '状态查看', icon: markRaw(Monitor), color: 'text-cyan-500' },
  { path: '/_sys/manager/permission', label: '权限管理', icon: markRaw(Setting), color: 'text-red-500' },
]

const recentPages = [
  { path: '/_sys/ai/chat', label: 'AI 聊天', icon: markRaw(ChatDotRound) },
  { path: '/_sys/database/todolist', label: '待办列表', icon: markRaw(DocumentCopy) },
  { path: '/_sys/manager/user', label: '用户管理', icon: markRaw(User) },
  { path: '/_sys/database/model_config', label: '模型配置', icon: markRaw(FolderOpened) },
]

const refreshData = () => {
  ElMessage.success('数据已刷新')
}
</script>
