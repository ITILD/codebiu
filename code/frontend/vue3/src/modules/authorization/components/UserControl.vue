<template>
  <el-dropdown trigger="click" items-center placement="bottom-end" @command="handleCommand">
    <UserLoginIcon pointer-default w-7 h-7 />
    <template #dropdown>
      <el-dropdown-menu>
        <!-- 用户信息 -->
        <el-dropdown-item command="profile" disabled>
          <div flex items-center>
            <UserLoginIcon m-2 w-8 h-8 />
            <div>
              <div text-lg font-5>{{ authState.user.username }}</div>
              <div text-sm text-note-sub>{{ authState.user.email }}</div>
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
import { markRaw, computed } from 'vue'
import { Monitor, Setting, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/common/stores/auth'
import { useVisibleMenu } from '@/common/composables/useMenu'
import UserLoginIcon from './UserLoginIcon.vue'

const router = useRouter()
const authStore = useAuthStore()
const authState = authStore.authState
const initAuthState = authStore.initAuthState
// 后台入口权限门禁: 至少持有一个声明权限的后台分组(如 sys/task/main:file)才显示
// "后台管理", 普通用户(无任何后台权限)完全看不到该入口
const { visibleMenuItems } = useVisibleMenu()
const canEnterAdmin = computed(() => visibleMenuItems.value.some((g) => Boolean(g.perm)))

interface MenuItem {
  command: string
  label: string
  icon: unknown
  divided?: boolean
  action?: () => void
}

const allMenuItems: MenuItem[] = [
  {
    command: 'admin',
    label: '后台管理',
    icon: markRaw(Monitor),
    divided: true,
    action: () => {
      router.push('/admin')
    },
  },
  {
    command: 'settings',
    label: '账户设置',
    icon: markRaw(Setting),
    action: () => {
      router.push('/setting')
    },
  },
  {
    command: 'logout',
    label: '退出登录',
    icon: markRaw(SwitchButton),
    divided: true,
    action: () => {
      initAuthState()
      router.push('/')
    },
  },
]

// 无任何后台菜单权限时剔除"后台管理"入口
const menuItems = computed<MenuItem[]>(() =>
  allMenuItems.filter((item) => item.command !== 'admin' || canEnterAdmin.value)
)

const handleCommand = (command: string) => {
  const item = menuItems.value.find((item) => item.command === command)
  if (item?.action) {
    item.action()
  }
}
</script>
