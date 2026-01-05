<template>
  <div bg-gray-500>
    <div flex gap-2>
      <!-- 语言选择 -->
      <select v-model="selectedLanguage">
        <option value="javascript">JavaScript</option>
        <option value="typescript">TypeScript</option>
        <option value="html">HTML</option>
        <option value="css">CSS</option>
        <option value="json">JSON</option>
        <option value="python">Python</option>
        <option value="java">Java</option>
        <option value="csharp">C#</option>
        <option value="cpp">C++</option>
        <option value="sql">SQL</option>
        <option value="markdown">Markdown</option>
        <option value="yaml">YAML</option>
        <option value="xml">XML</option>
      </select>

      <!-- 编码选择 -->
      <!-- <select v-model="selectedEncoding"
          class="border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="utf-8">UTF-8</option>
          <option value="utf-16">UTF-16</option>
          <option value="ascii">ASCII</option>
          <option value="iso-8859-1">ISO-8859-1</option>
        </select> -->

      <!-- 主题选择 -->

      <select v-model="selectedTheme">
        <option value="vs">Light</option>
        <option value="vs-dark">Dark</option>
        <option value="hc-black">High Contrast</option>
      </select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

// 定义属性（带默认值）
interface Props {
  modelLanguage?: string
  modelEncoding?: string
  modelTheme?: string
}

const props = withDefaults(defineProps<Props>(), {
  modelLanguage: 'javascript',
  modelEncoding: 'utf-8',
  modelTheme: 'vs',
})

// 定义 emit 事件
const emit = defineEmits<{
  (e: 'update:modelLanguage', value: string): void
  (e: 'update:modelEncoding', value: string): void
  (e: 'update:modelTheme', value: string): void
}>()

// computed 实现双向绑定
const selectedLanguage = computed({
  get: () => props.modelLanguage,
  set: (value: string) => emit('update:modelLanguage', value),
})

const selectedEncoding = computed({
  get: () => props.modelEncoding,
  set: (value: string) => emit('update:modelEncoding', value),
})

const selectedTheme = computed({
  get: () => props.modelTheme,
  set: (value: string) => emit('update:modelTheme', value),
})
</script>

<style scoped></style>
