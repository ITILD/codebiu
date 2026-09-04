<template>
  <!-- 多个设置 -->
  <!-- 基础设置 -->
  <SettingBase />
</template>

<script setup lang="ts">
// import { storeToRefs } from 'pinia'
import { SysSettingStore } from '@/common/stores/sys'
import { i18n, languageOptions } from '@/common/i18n/language'
const { sysStyle } = SysSettingStore()
</script>
