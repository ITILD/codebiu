<template>
  <!-- 网站页首: Logo/汉堡(左) + 主题切换/登录/头像(右) -->
  <header v-if="sysStyle.headFootShow">
    <div flex justify-between h-full>
      <!-- 左侧: 移动端汉堡(仅后台路由, 打开模块列表抽屉) -->
      <div flex items-center>
        <button
          v-if="isAdmin && !sysSettingStore.sysStyle.isMd"
          ml-3
          rounded-full
          hover:bg-note-tint
          p-2
          @click="sysSettingStore.sysStyle.isSidebarDrawerOpen = true"
        >
          <el-icon :size="22" text-note>
            <Menu />
          </el-icon>
        </button>

        <router-link to="/" flex items-center ml-4 md:ml-8>
          <img src="@/assets/img/ion/sy_w.svg" h-8 mr-3 />
          <span text-lg md:text-xl font-semibold whitespace-nowrap text-note>
            {{ TITLE }}
          </span>
        </router-link>
      </div>

      <!-- 右侧: 主题切换 + 登录/用户 -->
      <div flex items-center mr-4 md:mr-8 gap-3>
        <!-- 主题切换 -->
        <el-switch
          v-model="sysSettingStore.sysStyle.theme.isDark"
          @change="sysSettingStore.changeThemeValueByIsDark"
        />
        <!-- 登录/用户 -->
        <template v-if="authState.user.id">
          <UserControl />
        </template>
        <template v-else>
          <button
            flex
            items-center
            justify-center
            rounded
            px-3
            py-1.5
            text-note
            hover:bg-note-tint
            transition-colors
            @click="showLoginDialog = true"
          >
            <!-- 登录 -->
            {{ $t('sign_in') }}
          </button>
          <!-- 注册按钮 小屏幕隐藏 -->
          <button
            max-lg:hidden
            flex
            items-center
            justify-center
            rounded
            px-3
            py-1.5
            border-1
            border-note
            text-note
            hover:bg-note-tint
            transition-colors
            @click="showRegisterDialog = true"
          >
            {{ $t('sign_up') }}
          </button>

          <!-- 登录弹窗 -->
          <LoginDialog
            v-model="showLoginDialog"
            @login="handleLogin"
            @register="showRegisterDialog = true; showLoginDialog = false"
          />

          <!-- 注册弹窗 -->
          <RegisterDialog
            v-model="showRegisterDialog"
            @register-success="handleRegisterSuccess"
            @back-to-login="showRegisterDialog = false; showLoginDialog = true"
          />
        </template>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
// 样式控制
import { SysSettingStore } from '@/stores/sys'
import { Menu } from '@element-plus/icons-vue'
import LoginDialog from './head/LoginDialog.vue'
import RegisterDialog from './head/RegisterDialog.vue'
import UserControl from './head/UserControl.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthResponse } from '@/types/authorization/auth'
const authStore = useAuthStore()
const authState = authStore.authState
const sysSettingStore = SysSettingStore()
const sysStyle = sysSettingStore.sysStyle
const showLoginDialog = ref(false)
const showRegisterDialog = ref(false)
const TITLE = ref(import.meta.env.VITE_GLOB_APP_TITLE)

const route = useRoute()
const router = useRouter()
// 仅后台路由显示汉堡(打开侧边栏抽屉)
const isAdmin = computed(() => route.path.startsWith('/_sys'))

// 未登录被拦截回首页时自动弹出登录框
watch(
  () => route.query.login,
  (v) => {
    if (v === '1') showLoginDialog.value = true
  },
  { immediate: true },
)

// 处理登录
const handleLogin = (authResponse: AuthResponse) => {
  authStore.setAuthState(authResponse)
  // 登录后拉取角色与权限码(侧边栏菜单/按钮权限的过滤依据)
  authStore.fetchPermissions()
  // 清理登录引导参数, 避免再次进入首页重复弹出登录框
  if (route.query.login) {
    const { login: _login, ...rest } = route.query
    router.replace({ query: rest })
  }
}

// 处理注册成功
const handleRegisterSuccess = (authResponse: AuthResponse) => {
  // 注册成功后自动登录
  authStore.setAuthState(authResponse)
  // 拉取新账户的角色与权限码
  authStore.fetchPermissions()
}
</script>
