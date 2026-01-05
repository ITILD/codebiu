<template>
  <el-dropdown trigger="click" items-center placement="bottom-end" @command="handleCommand">
    <UserLoginIcon pointer-default w-7 h-7 />
    <template #dropdown>
      <el-dropdown-menu>
        <!-- 用户信息 -->
        <el-dropdown-item command="profile">
          <div flex items-center>
            <UserLoginIcon m-2 w-8 h-8 />
            <div>
              <div text-lg font-5>Name User</div>
              <div text-sm text-gray-500>**@***.com</div>
            </div>
          </div>
        </el-dropdown-item>

        <!-- 菜单项 -->
        <el-dropdown-item v-for="item in menuItems" :key="item.command" :command="item.command" :divided="item.divided">
          <el-icon class="mr-2">
            <component :is="item.icon" />
          </el-icon>
          {{ item.label }}
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>

</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import { FolderOpened, Setting, Monitor, EditPen, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { SysSettingStore } from '@/stores/sys'

// 获取路由和存储实例
const router = useRouter()
const authStore = useAuthStore()
const initAuthState = authStore.initAuthState
const sysSettingStore = SysSettingStore()

// 定义菜单项类型
interface MenuItem {
  command: string
  label: string
  icon: unknown
  divided?: boolean
  action?: () => void
}

// 菜单项配置
const menuItems: MenuItem[] = [
  {
    command: 'projects',
    label: '项目列表',
    icon: markRaw(FolderOpened),
    action: () => {
      // 跳转到项目列表页面
      router.push('/projects')
    },
  },
  {
    command: 'blog',
    label: '博客记录',
    icon: markRaw(EditPen),
    action: () => {
      router.push('/blog')
    },
  },
  {
    command: 'settings',
    divided: true,
    label: '设置',
    icon: markRaw(Setting),
    action: () => {
      sysSettingStore.isSysSettingShow = true
    },
  },
  {
    command: 'admin',
    label: '后台管理',
    icon: markRaw(Monitor),
    action: () => {
      router.push('/_sys')
    },
  },
  {
    command: 'dev',
    label: '开发测试',
    icon: markRaw(EditPen),
    action: () => {
      router.push('/_dev')
    },
  },
  {
    command: 'logout',
    label: '退出登录',
    icon: markRaw(SwitchButton),
    // divided 分隔线
    divided: true,
    action: () => {
      // 退出登录，重置用户状态
      initAuthState()
    },
  },
]

const handleCommand = (command: string) => {
  const item = menuItems.find((item) => item.command === command)
  if (item?.action) {
    item.action()
  }
}

</script>

<style scoped></style>
