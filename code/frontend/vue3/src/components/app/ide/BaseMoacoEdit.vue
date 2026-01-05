<template>
  <div ref="editorContainer"></div>
</template>

<script setup lang="ts">
// import { editor } from '@monaco-editor/loader'
import * as monaco from 'monaco-editor'
// 定义组件属性
interface Props {
  modelValue?: string
  language?: string
  theme?: 'vs' | 'vs-dark' | 'hc-black'
  encoding?: string
  readOnly?: boolean
  fontSize?: number
  lineHeight?: number
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  language: 'javascript',
  theme: 'vs',
  encoding: 'utf-8',
  readOnly: false,
  fontSize: 14,
  lineHeight: 1.5
})

// 定义事件
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'change': [value: string]
}>()

// 编辑器实例和容器引用
const editorContainer = ref<HTMLElement | null>(null)
let monacoEditor: any = null

// 初始化编辑器
onMounted(async () => {
  if (editorContainer.value) {
    // const monaco = await import('monaco-editor')

    monacoEditor = monaco.editor.create(editorContainer.value, {
      value: props.modelValue,
      language: props.language,
      theme: props.theme,
      readOnly: props.readOnly,
      fontSize: props.fontSize,
      lineHeight: props.lineHeight,
      automaticLayout: true,
      minimap: { enabled: true },
      scrollBeyondLastLine: false,
      wordWrap: 'on'
    })

    // 监听编辑器内容变化
    monacoEditor.onDidChangeModelContent(() => {
      const value = monacoEditor.getValue()
      emit('update:modelValue', value)
      emit('change', value)
    })
  }
})

// 在组件卸载前销毁编辑器
onBeforeUnmount(() => {
  if (monacoEditor) {
    monacoEditor.dispose()
  }
})

// 监听属性变化
watch(() => props.modelValue, (newValue) => {
  if (monacoEditor && monacoEditor.getValue() !== newValue) {
    monacoEditor.setValue(newValue)
  }
})

watch(() => props.language, (newLanguage) => {
  if (monacoEditor) {
    const model = monacoEditor.getModel()
    if (model) {
      monaco.editor.setModelLanguage(model, newLanguage)
    }
  }
})

watch(() => props.theme, (newTheme) => {
  if (monacoEditor) {
    monaco.editor.setTheme(newTheme)
  }
})

// 创建TextDecoder
// const decoder = new TextDecoder("utf-8");


// 暴露方法给父组件
defineExpose({
  getInstance: () => monacoEditor,
  setValue: (value: string) => {
    if (monacoEditor) {
      monacoEditor.setValue(value)
    }
  },
  getValue: (): string => {
    return monacoEditor ? monacoEditor.getValue() : ''
  },
  updateOptions: (options: any) => {
    if (monacoEditor) {
      monacoEditor.updateOptions(options)
    }
  }
})
</script>

<style scoped></style>
