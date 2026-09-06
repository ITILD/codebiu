<template>
  <!-- 商务风主题展示页 -->
  <ThemeShowcase :theme="business" />
</template>

<script setup lang="ts">
// 商务风主题子页面: 藏蓝主色 + 冷灰界面的组件样式演示
import ThemeShowcase from '../../components/playground/ThemeShowcase.vue'
import { playgroundThemes } from '../../components/playground/themes'

const business = playgroundThemes.find((t) => t.key === 'business')!
</script>
