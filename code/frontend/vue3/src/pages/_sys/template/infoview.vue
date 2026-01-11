<template>
  <!-- 系统用到的文本图表展示 -->
  <div p-2 w-full flex>
    <!--左侧树状 选择器 -->
    <div w-60><el-tree :data="data" :props="defaultProps" @node-click="handleNodeClick" /></div>

    <!--右侧 Monaco 编辑器 -->
    <div flex-1 mb-4 flex flex-col>
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
const LazyBaseMoacoEdit = defineAsyncComponent(
  () => import('@/components/app/ide/BaseMoacoEdit.vue'),
)
const LazyBaseMoacoEditControl = defineAsyncComponent(
  () => import('@/components/app/ide/BaseMoacoEditControl.vue'),
)
import { CodeType } from '@/common/enum/code'
// 所有状态
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 语言选择
const selectedLanguage = ref(CodeType.json)

// 导入系统设置 Store
import { SysSettingStore } from '@/stores/sys'

const sysStore = SysSettingStore()

// 主题选择
const selectedTheme = computed(() => (sysStore.sysStyle.theme.isDark ? 'vs-dark' : 'vs'))

// 编码选择
const selectedEncoding = ref('utf-8')

// 编辑器内容（用于双向绑定测试）
const editorContent = ref(``)

// 加载示例代码
const handleLoadSample = (lang: CodeType, code: string) => {
  selectedLanguage.value = lang
  editorContent.value = code
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
  const label = data.label
  switch (label) {
    case 'authStore':
      handleLoadSample(CodeType.json, JSON.stringify(authStore, null, 2))
      break
    default:
      editorContent.value = ''
      break
  }
}
const defaultProps = {
  children: 'children',
  label: 'label',
}
const data: Tree[] = [
  {
    label: 'pina store',
    children: [
      {
        label: 'authStore',
      },
    ],
  },
  {
    label: 'localstorage',
  },
]
</script>

<style scoped></style>
