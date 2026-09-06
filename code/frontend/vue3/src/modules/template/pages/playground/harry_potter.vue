<template>
  <!-- 哈利波特主题展示页 -->
  <ThemeShowcase :theme="harryPotter" />
</template>

<script setup lang="ts">
// 哈利波特主题子页面: 羊皮纸底 + 鎏金主色的组件样式演示
import ThemeShowcase from '../../components/playground/ThemeShowcase.vue'
import { playgroundThemes } from '../../components/playground/themes'

const harryPotter = playgroundThemes.find((t) => t.key === 'harry_potter')!
</script>
