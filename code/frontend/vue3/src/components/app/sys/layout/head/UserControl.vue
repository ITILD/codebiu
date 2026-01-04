<template>
  <el-dropdown-menu>
    <!-- 用户信息 -->
    <el-dropdown-item command="profile">
      <div flex items-center>
        <UserLogin m-2 w-8 h-8 />
        <div>
          <div text-lg font-5>Name User</div>
          <div text-sm text-gray-500>**@***.com</div>
        </div>
      </div>
    </el-dropdown-item>

    <!-- 菜单项 -->
    <el-dropdown-item
      v-for="item in menuItems"
      :key="item.command"
      :command="item.command"
      :divided="item.divided"
    >
      <el-icon class="mr-2">
        <component :is="item.icon" />
      </el-icon>
      {{ item.label }}
    </el-dropdown-item>
  </el-dropdown-menu>
</template>

<script setup lang="ts">
import { FolderOpened, Setting, Monitor, EditPen, SwitchButton } from '@element-plus/icons-vue'
import { UserStore } from '@/stores/user'
import { SysSettingStore } from '@/stores/sys'

// 获取路由和存储实例
const router = useRouter()
const userStore = UserStore()
const userState = userStore.userState
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
    icon: FolderOpened,
    action: () => {
      // 处理项目列表点击
      console.log('点击项目列表')
    },
  },
  {
    command: 'blog',
    label: '博客记录',
    icon: EditPen,
    action: () => {
      router.push('/blog')
    },
  },
  {
    command: 'settings',
    divided: true,
    label: '设置',
    icon: Setting,
    action: () => {
      sysSettingStore.isSysSettingShow = true
    },
  },
  {
    command: 'admin',
    label: '后台管理',
    icon: Monitor,
    action: () => {
      router.push('/_server')
    },
  },
  {
    command: 'dev',
    label: '开发测试',
    icon: EditPen,
    action: () => {
      router.push('/_dev')
    },
  },
  {
    command: 'logout',
    label: '退出登录',
    icon: SwitchButton,
    // divided 分隔线
    divided: true,
    action: () => {
      // 访问瑞出api

      // 退出登录
      userState.isLogin = false
    },
  },
]

// 处理菜单项点击
const handleMenuClick = (command: string) => {
  const item = menuItems.find((item) => item.command === command)
  if (item && item.action) {
    item.action()
  }
}

// 暴露处理函数给父组件使用
defineExpose({
  handleMenuClick,
})
</script>

<style scoped>
.el-dropdown-menu__item {
  display: flex;
  align-items: center;
}
</style>
