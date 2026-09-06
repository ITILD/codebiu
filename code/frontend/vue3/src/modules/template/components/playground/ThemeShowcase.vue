<template>
  <!-- 主题根容器: style 注入 CSS 变量, 整页 Element Plus 组件自动换肤 -->
  <div :style="{ ...theme.vars, fontFamily: 'var(--el-font-family)' }" :class="theme.rootClass"
    class="rounded-lg p-4 md:p-6 overflow-hidden">
    <!-- 主题横幅 -->
    <div :class="theme.bannerClass" rounded p-4 mb-4>
      <h3 text-lg font-bold>{{ theme.name }}</h3>
      <p text-sm mt-1 opacity-80>{{ theme.desc }}</p>
    </div>

    <!-- 按钮 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>按钮 Button</span>
      </template>
      <div flex flex-wrap items-center gap-3>
        <el-button type="primary">主要按钮</el-button>
        <el-button>默认按钮</el-button>
        <el-button type="success">成功</el-button>
        <el-button type="warning">警告</el-button>
        <el-button type="danger">危险</el-button>
        <el-button type="info">信息</el-button>
        <el-button type="primary" plain>朴素</el-button>
        <el-button round>圆角</el-button>
        <el-button disabled>禁用</el-button>
      </div>
    </el-card>

    <!-- 标签 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>标签 Tag</span>
      </template>
      <div flex flex-wrap items-center gap-3>
        <el-tag>默认</el-tag>
        <el-tag type="success">成功</el-tag>
        <el-tag type="warning">警告</el-tag>
        <el-tag type="danger">危险</el-tag>
        <el-tag type="info">信息</el-tag>
        <el-tag type="primary" effect="dark">实底</el-tag>
        <el-tag type="primary" effect="plain">朴素</el-tag>
        <el-tag round>圆角</el-tag>
      </div>
    </el-card>

    <!-- 表单控件 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>表单控件</span>
      </template>
      <div class="grid gap-3 md:grid-cols-2">
        <el-input v-model="input" placeholder="输入框" clearable />
        <el-select v-model="select" placeholder="下拉选择">
          <el-option v-for="s in options" :key="s" :label="s" :value="s" />
        </el-select>
        <div flex items-center gap-3>
          <span text-sm>开关</span>
          <el-switch v-model="on" />
        </div>
        <div flex items-center gap-3>
          <span text-sm>评分</span>
          <el-rate v-model="rate" />
        </div>
        <div flex items-center gap-3 class="md:col-span-2">
          <span text-sm whitespace-nowrap>滑块 {{ slider }}</span>
          <el-slider v-model="slider" />
        </div>
      </div>
    </el-card>

    <!-- 提示 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>提示 Alert</span>
      </template>
      <div flex flex-col gap-2>
        <el-alert title="信息提示" type="info" show-icon :closable="false" />
        <el-alert title="成功提示" type="success" show-icon :closable="false" />
        <el-alert title="警告提示" type="warning" show-icon :closable="false" />
        <el-alert title="错误提示" type="error" show-icon :closable="false" />
      </div>
    </el-card>

    <!-- 描述列表 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>描述列表 Descriptions</span>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="主题">{{ theme.name }}</el-descriptions-item>
        <el-descriptions-item label="主色">
          <el-tag size="small">{{ theme.colors[0] }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="用途">组件样式选型</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>表格 Table</span>
      </template>
      <el-table :data="rows" border stripe size="small">
        <el-table-column prop="name" label="组件" min-width="120" />
        <el-table-column prop="status" label="状态" min-width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === '推荐' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" min-width="160" />
      </el-table>
    </el-card>

    <!-- 进度与页签 -->
    <el-card shadow="never" mb-4>
      <template #header>
        <span font-semibold>进度 Progress 与页签 Tabs</span>
      </template>
      <el-progress :percentage="60" />
      <el-progress :percentage="100" status="success" />
      <el-tabs mt-2>
        <el-tab-pane label="页签一">当前主题下页签一的内容样式。</el-tab-pane>
        <el-tab-pane label="页签二">当前主题下页签二的内容样式。</el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 对话框 -->
    <el-card shadow="never">
      <template #header>
        <span font-semibold>对话框 Dialog</span>
      </template>
      <el-button type="primary" @click="dialog = true">打开对话框</el-button>
      <el-dialog v-model="dialog" title="主题化对话框" width="90%" class="max-w-[420px]">
        <p text-sm>对话框在当前主题下渲染(非 append-to-body)，配色随主题变化。</p>
        <template #footer>
          <el-button @click="dialog = false">取消</el-button>
          <el-button type="primary" @click="dialog = false">确认</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// 主题化组件展示: 同一套常用组件, 依据传入主题换肤, 供跨主题对比选型
import type { PlaygroundTheme } from './themes'

/** 当前展示的主题 */
defineProps<{ theme: PlaygroundTheme }>()

// 表单控件演示值
const input = ref('')
const select = ref('')
const options = ['选项一', '选项二', '选项三']
const on = ref(true)
const rate = ref(4)
const slider = ref(40)

// 对话框显隐
const dialog = ref(false)

// 表格静态数据
const rows = [
  { name: 'el-button', status: '推荐', note: '按钮' },
  { name: 'el-card', status: '推荐', note: '内容卡片容器' },
  { name: 'el-table', status: '可选', note: '数据表格' },
]
</script>
