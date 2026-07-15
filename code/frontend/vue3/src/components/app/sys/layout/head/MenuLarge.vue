<template>
  <el-menu :default-active="routerStore.routerPath.now" :router="true" :mode="mode ? 'horizontal' : 'vertical'"
    :ellipsis="false">
    <el-menu-item index="/">首页</el-menu-item>
    <el-menu-item index="/_sys">管理后台</el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { RouterStore } from '@/stores/router'

const routerStore = RouterStore()

defineProps({
  mode: {
    type: Boolean,
    default: true
  }
})
</script>
