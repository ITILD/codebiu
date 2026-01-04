<template>
  <div ml-2>
    <div v-if="authState.img">
      <img w-full h-full :src="authState.img" alt="" srcset="" />
    </div>
    <!--游客图标 -->
    <!-- <UserSVG w-full h-full v-else /> -->
    <el-avatar :size="30" :icon="UserFilled" v-else  />
  </div>
</template>
<script setup lang="ts">
// 样式控制
import { UserFilled } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
const authState = authStore.authState
/**
 * 用户头像 登陆状态
 */
onMounted(() => { })
</script>
<style scoped></style>
