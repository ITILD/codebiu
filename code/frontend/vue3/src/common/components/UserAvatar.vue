<template>
  <!-- 全局统一的用户头像: 有图片地址时显示图片, 否则显示用户名首字默认头像 -->
  <el-avatar v-if="src" :size="size" :src="src" />
  <!-- 默认头像: 取展示名首字(中文取首字, 英文取首字母大写), 按名字哈希取柔和配色 -->
  <el-avatar v-else-if="initial" :size="size" :style="initialStyle" class="select-none">
    {{ initial }}
  </el-avatar>
  <!-- 无名字兜底: 默认用户图标 -->
  <el-avatar v-else :size="size" :icon="UserFilled" />
</template>

<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'

const props = withDefaults(defineProps<{
  /** 头像图片地址(为空时显示默认首字头像) */
  src?: string | null
  /** 展示名(昵称/用户名, 用于默认首字头像; 为空回退默认用户图标) */
  name?: string | null
  /** 头像尺寸(px) */
  size?: number
}>(), { size: 32 })

/** 默认首字头像柔和配色组(淡绿自然笔记风格, 按名字哈希稳定取色) */
const PALETTE = [
  { bg: '#d9f2e5', fg: '#2f7d5d' },
  { bg: '#e3edda', fg: '#5a7d3a' },
  { bg: '#dcedf5', fg: '#3a6f8f' },
  { bg: '#f5ecd8', fg: '#8f6b3a' },
  { bg: '#f0e3f5', fg: '#6f4a8f' },
  { bg: '#f5e0e0', fg: '#8f3a3a' },
]

/** 取展示名首字: 中文取第一个字, 英文/数字取首字母大写 */
const initial = computed(() => {
  const name = (props.name || '').trim()
  if (!name) return ''
  const codePoint = name.codePointAt(0) ?? 0
  return String.fromCodePoint(codePoint).toUpperCase()
})

/** 按名字哈希稳定选取配色(同一用户始终同色) */
const initialStyle = computed(() => {
  const name = (props.name || '').trim()
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  }
  const color = PALETTE[hash % PALETTE.length]
  return { backgroundColor: color.bg, color: color.fg, fontWeight: 600 }
})
</script>
