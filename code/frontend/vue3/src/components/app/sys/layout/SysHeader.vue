<template>
  <!-- 网站页首区域 -->
  <header v-if="sysStyle.headFootShow">
    <!-- justify-between 主轴上均匀分布 第一个项目靠左，最后一个项目靠右，其余项目平均分布剩余空间-->
    <div flex justify-between h-full>
      <!--小汉堡菜单 小屏幕：最左侧显示 -->
      <button md:hidden m-4 rounded-full hover:bg-gray-100 dark:hover:bg-gray-700
        @click="showMobileMenu = !showMobileMenu">
        <el-icon :size="40">
          <Menu />
        </el-icon>
      </button>

      <el-drawer v-model="showMobileMenu" title="服务菜单" direction="ltr" size="70%">
        <MenuLarge max-h-14 :mode="false" />
      </el-drawer>



      <div flex m-0 md:mx-4 lg:mx-12>
        <!--网站Logo和名称 大屏幕：最左侧 小屏幕：中间-->
        <router-link to="/" flex m-6 md:m-3>
          <img src="@/assets/img/ion/sy_w.svg" h-8 mr-3 />
          <span text-6 font-semibold whitespace-nowrap>{{ TITLE }}</span>
        </router-link>
        <!-- 大选择菜单 大屏幕：顺序左 小屏幕：隐藏-->
        <div max-md:hidden ml-4>
          <MenuLarge max-h-14 />
        </div>
      </div>
      <!--中间 空标题 可以加装饰 -->
      <!-- <span left-0 right-0 m-auto></span> -->
      <!-- 搜索/登陆/注册/登陆后图标导航 -->
      <div flex m-3>
        <!-- 搜索组件 小屏幕：隐藏 -->
        <div max-md:hidden mr-4>
          <el-input v-model="searchText" :placeholder="$t('search') + '...'" rounded-full clearable>
            <template #prefix>
              <el-icon>
                <Search />
              </el-icon>
            </template>
          </el-input>
        </div>

        <!-- 主题切换 -->
        <ButtonSwitch v-model="sysSettingStore.sysStyle.theme.isDark"
          @change="sysSettingStore.changeThemeValueByIsDark" />
        <!-- 登录/用户 -->
        <template v-if="isLogin">
          <!-- 用户图标 -->
          <UserLogin @click="sysStyle.isUserControlShow = !sysStyle.isUserControlShow" pointer-default w-7 h-7 />
          <!-- 大屏幕下 点击用户图标下拉 导航栏-->
          <MinPopover v-model="sysStyle.isUserControlShow">
            <ShowHidden v-show="sysStyle.isUserControlShow">
              <UserControl absolute z-10 w-60 right-2 top-14 rounded-lg bg-deep-0 p-4 text-xl shadow-xl />
            </ShowHidden>
          </MinPopover>
        </template>
        <template v-else>
          <button flex items-center justify-center hover:shadow mx-1 hover:bg-deep-3 @click="showLoginDialog = true">
            <span text-deep-2 px-2 py-1 w-18>
              <!-- 登录 -->
              {{ $t('sign_in') }}
            </span>
          </button>
          <!-- 注册按钮  小屏幕：隐藏 -->
          <button max-lg:hidden flex items-center justify-center shadow mx-1 border-1 border-gray-300 hover:bg-deep-3
            @click="handleRegister">
            <span text-deep-2 px-2 py-1 w-18>
              {{ $t('sign_up') }}
            </span>
          </button>

          <!-- 登录弹窗 -->
          <LoginDialog v-model="showLoginDialog" @login="handleLogin" @register="handleRegister" />

          <!-- 注册弹窗 -->
          <RegisterDialog v-model="showRegisterDialog" @register-success="handleRegisterSuccess"
            @back-to-login="showRegisterDialog = false; showLoginDialog = true" />
        </template>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
// 样式控制
import { SysSettingStore } from '@/stores/sys'
import { Search, Menu } from '@element-plus/icons-vue'
import LoginDialog from './head/LoginDialog.vue'
import RegisterDialog from './head/RegisterDialog.vue'

const sysSettingStore = SysSettingStore()
const sysStyle = sysSettingStore.sysStyle
const showMobileMenu = ref(false)
const isLogin = ref(false)
const showLoginDialog = ref(false)
const showRegisterDialog = ref(false)
const TITLE = ref(import.meta.env.VITE_GLOB_APP_TITLE)
// 搜索
const searchText = ref('')
// 处理登录
const handleLogin = (userInfo: { username: string }) => {
  // 设置登录状态
  isLogin.value = true
  console.log('用户登录成功:', userInfo)
  // 这里可以添加登录后的逻辑，比如保存用户信息到store等
}

// 处理注册
const handleRegister = () => {
  showLoginDialog.value = false
  showRegisterDialog.value = true
  console.log('跳转到注册页面')
  // 这里可以添加跳转到注册页面的逻辑
}

// 处理注册成功
const handleRegisterSuccess = (userInfo: { username: string }) => {
  // 注册成功后自动登录
  isLogin.value = true
  showRegisterDialog.value = false
  console.log('注册成功:', userInfo)
  // 这里可以添加注册成功后的逻辑，比如自动登录等
}
</script>

<style scoped></style>
