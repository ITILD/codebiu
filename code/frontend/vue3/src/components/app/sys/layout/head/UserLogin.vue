<template>
  <div>
    <div v-if="userState.img">
      <img w-full h-full src="" alt="" srcset="" />
    </div>
    <!--游客图标 -->
    <UserSVG w-full h-full v-else />
  </div>
</template>
<script setup lang="ts">
// 样式控制
import { UserStore } from '@/stores/user'
const userStore = UserStore()
const userState = userStore.userState
/**
 * 用户头像 登陆状态
 */
onMounted(() => {})
</script>
<style scoped></style>
