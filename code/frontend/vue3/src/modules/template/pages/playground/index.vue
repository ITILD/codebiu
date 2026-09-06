<template>
  <!-- 主题总览: 卡片式主题选择入口, 点击进入对应主题子页面 -->
  <div grid gap-4 class="sm:grid-cols-2 lg:grid-cols-3">
    <el-card v-for="t in playgroundThemes" :key="t.key" shadow="hover" cursor-pointer @click="router.push(t.path)">
      <div flex flex-col gap-2>
        <div flex items-center justify-between>
          <span font-semibold text-note>{{ t.name }}</span>
          <div flex gap-1>
            <span v-for="c in t.colors" :key="c" class="h-4 w-4 rounded-full border border-note" :style="{ background: c }" />
          </div>
        </div>
        <p text-xs text-note-sub>{{ t.desc }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// 主题选择页(组件选型子页面): 展示可切换的主题卡片
import { playgroundThemes } from '../../components/playground/themes'

const router = useRouter()
</script>
