<template>
  <div ml-2>
    <!-- 用户头像(公共组件, 与设置页预览样式一致; 无头像时显示首字默认头像) -->
    <UserAvatar
      :size="30"
      :src="authState.user.avatar"
      :name="authState.user.nickname || authState.user.username"
    />
  </div>
</template>
<script setup lang="ts">
import { useAuthStore } from '@/common/stores/auth'
const authStore = useAuthStore()
const authState = authStore.authState
/**
 * 用户头像 登陆状态
 */
onMounted(() => { })
</script>
