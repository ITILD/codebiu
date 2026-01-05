<template>
  <div p-2 w-full flex>
    <!--左侧树状 选择器 -->
    <div w-60><el-tree :data="data" :props="defaultProps" @node-click="handleNodeClick" /></div>

    <!--右侧 Monaco 编辑器 -->
    <div flex-1 mb-4 bg-gray-100 p-2 flex flex-col>
      <!-- up: 9/10 -->
      <LazyBaseMoacoEdit
        class="h-19/20"
        bg-gray-300
        v-model="editorContent"
        :language="selectedLanguage"
        :theme="selectedTheme"
        :encoding="selectedEncoding"
        :font-size="14"
        :line-height="1.5"
      />
      <!-- down: 剩余 1/10 -->
      <LazyBaseMoacoEditControl
        flex-1
        v-model:modelLanguage="selectedLanguage"
        v-model:modelEncoding="selectedEncoding"
        v-model:modelTheme="selectedTheme"
        @loadSample="handleLoadSample"
        @clear="clearEditor"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
const LazyBaseMoacoEdit = defineAsyncComponent(
  () => import('@/components/app/ide/BaseMoacoEdit.vue'),
)
const LazyBaseMoacoEditControl = defineAsyncComponent(
  () => import('@/components/app/ide/BaseMoacoEditControl.vue'),
)
// 语言选择
const selectedLanguage = ref('json')

// 主题选择
const selectedTheme = ref('vs')

// 编码选择
const selectedEncoding = ref('utf-8')

// 编辑器内容（用于双向绑定测试）
const editorContent = ref(``)

// 加载示例代码
const handleLoadSample = (lang: string, code: string) => {
  editorContent.value = code
  selectedLanguage.value = lang
}

// 清空编辑器
const clearEditor = () => {
  editorContent.value = ''
}

interface Tree {
  label: string
  children?: Tree[]
}

const handleNodeClick = (data: Tree) => {
  console.log(data)
}
const defaultProps = {
  children: 'children',
  label: 'label',
}
const data: Tree[] = [
  {
    label: 'Level one 1',
    children: [
      {
        label: 'Level two 1-1',
        children: [
          {
            label: 'Level three 1-1-1',
          },
        ],
      },
    ],
  },
]
</script>

<style scoped></style>
