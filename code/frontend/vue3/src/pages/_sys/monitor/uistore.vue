<template>
  <div flex overflow-hidden h-full>
    <!--左侧树状 选择器 -->
    <div w-60  h-full><el-tree :data="data" :props="defaultProps" @node-click="handleNodeClick" /></div>

    <!--右侧 Monaco 编辑器 -->
    <div flex-1 flex flex-col overflow-auto h-full>
      <Suspense>
        <template #default>
          <LazyBaseMoacoEdit flex-1 min-h-10 min-w-160 v-model="editorContent" :language="selectedLanguage"
            :theme="selectedTheme" :encoding="selectedEncoding" :font-size="14" :line-height="1.5" />
        </template>
        <template #fallback>
          <!-- 骨架屏 -->
          <div flex-1 flex flex-col p-4>
            <el-skeleton :rows="10" animated />
          </div>
        </template>
      </Suspense>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Suspense } from 'vue'

const LazyBaseMoacoEdit = defineAsyncComponent(
  () => import('@/components/app/ide/BaseMoacoEdit.vue'),
)
import type Node from 'element-plus/es/components/tree/src/model/node'
//
import {getLocalStorageKeys} from '@/common/utils/database/localstorage'

import { CodeType } from '@/common/enum/code'
// 所有状态
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// 导入系统设置 Store
import { SysSettingStore } from '@/stores/sys'

const sysSettingStore = SysSettingStore()

// 主题选择
const selectedTheme = computed(() => (sysSettingStore.sysStyle.theme.isDark ? 'vs-dark' : 'vs'))

// 语言选择
const selectedLanguage = ref(CodeType.json)

// 编码选择
const selectedEncoding = ref('utf-8')

// 编辑器内容（用于双向绑定测试）
const editorContent = ref(``)

// 加载示例代码
const handleLoadSample = (lang: CodeType, code: string) => {
  selectedLanguage.value = lang
  editorContent.value = code
}

interface Tree {
  label: string
  children?: Tree[]
}

// 树状节点点击事件处理函数
const handleNodeClick = (data: Tree, node: Node) => {
  const label = data.label
  debugger
  switch (label) {
    case 'authStore':
      handleLoadSample(CodeType.json, JSON.stringify(authStore, null, 2))
      return
    case 'sysSettingStore':
      handleLoadSample(CodeType.json, JSON.stringify(sysSettingStore, null, 2))
      return
  }
  // 如果不在以上几种情况,判断父节点是不是localstorage
  if (node.parent?.data.label === 'localstorage') {
    // localStorage 里获取label 对应的value 注意格式化json字符串
    const value = localStorage.getItem(node.data.label)
    if (value === null) return

    try {
      // 尝试解析 JSON，如果成功则格式化输出
      const parsedValue = JSON.parse(value)
      handleLoadSample(CodeType.json, JSON.stringify(parsedValue, null, 2))
    } catch {
      // 解析失败说明是普通字符串，直接处理
      handleLoadSample(CodeType.json, value)
    }
  }
}



// 使用
const localStorageKeys = getLocalStorageKeys()
//  符合tree的子列表
const localStorageKeysInTree = localStorageKeys.map(key => ({ label: key, }))

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
      {
        label: 'sysSettingStore',
      },
    ],
  },
  {
    label: 'localstorage',
    children: localStorageKeysInTree,
  },
]
</script>

<style scoped></style>
