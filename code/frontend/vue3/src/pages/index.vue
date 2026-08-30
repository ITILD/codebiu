<template>
  <div w-full max-w-5xl mx-auto p-4 md:p-8>
    <!-- Hero: 自然笔记卡片(苔绿渐变+笔记本格线) -->
    <section
      relative
      overflow-hidden
      rounded-2xl
      border-note
      bg-note-gradient
      p-8
      md:p-14
      mb-10
    >
      <!-- 笔记本横线纹理 -->
      <div absolute inset-0 note-lined-paper pointer-events-none />
      <!-- 右上角叶片装饰 -->
      <div absolute top-4 right-6 text-4xl md:text-5xl opacity-70 dark:opacity-90 select-none>🌿</div>

      <div relative>
        <h1 font-serif text-3xl md:text-5xl font-bold text-note-green mb-4>
          {{ TITLE }}
        </h1>
        <p text-base md:text-lg text-note-sub mb-2 max-w-xl leading-relaxed>
          像打理一页自然笔记一样,安放你的数据与灵感。
        </p>
        <p text-sm md:text-base text-note-sub mb-8 max-w-xl>
          登录后点击右上角头像,即可进入后台管理工作台。
        </p>
        <RouterLink
          to="/_sys"
          inline-flex
          items-center
          gap-2
          px-6
          py-2.5
          rounded-full
          bg-note-green
          text-white
          font-medium
          transition-all
          duration-300
          hover:opacity-90
          hover:-translate-y-0.5
          hover:shadow-note
        >
          <el-icon><Promotion /></el-icon>
          进入工作台
        </RouterLink>
      </div>
    </section>

    <!-- 功能模块入口卡片 -->
    <section>
      <div flex items-center gap-2 mb-6>
        <span text-xl>📖</span>
        <h2 font-serif text-2xl font-semibold text-note>功能模块</h2>
        <div flex-1 border-b border-dashed border-note />
      </div>

      <div grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5>
        <RouterLink
          v-for="module in modules"
          :key="module.title"
          :to="module.to"
          bg-note-card
          border
          border-note
          rounded-xl
          p-6
          transition-all
          duration-300
          hover:-translate-y-1
          hover:shadow-note
          hover:border-note-green
        >
          <div
            flex
            items-center
            justify-center
            w-11
            h-11
            rounded-full
            bg-note-tint
            text-note-green
            mb-4
          >
            <el-icon :size="22"><component :is="module.icon" /></el-icon>
          </div>
          <h3 text-lg font-semibold text-note mb-2>{{ module.title }}</h3>
          <p text-sm text-note-sub leading-relaxed>{{ module.desc }}</p>
        </RouterLink>
      </div>
    </section>

    <!-- 底部小语 -->
    <section mt-12 text-center>
      <p text-sm text-note-sub font-serif italic>
        「 淡淡的绿意,是数据生长的样子 」
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { markRaw } from 'vue'
import {
  Monitor,
  Collection,
  FolderOpened,
  ChatDotRound,
  Document,
  Files,
  Promotion,
} from '@element-plus/icons-vue'

const TITLE = import.meta.env.VITE_GLOB_APP_TITLE

// 功能模块入口(与左侧边栏目录对应)
const modules = [
  {
    title: '系统概览',
    desc: '纵览系统运行状态与关键指标。',
    to: '/_sys',
    icon: markRaw(Monitor),
  },
  {
    title: '知识库',
    desc: '项目、文档、成员与问答,一处管理。',
    to: '/_sys/rag/project',
    icon: markRaw(Collection),
  },
  {
    title: '文件管理',
    desc: '虚拟文件系统,目录式浏览与秒传。',
    to: '/_sys/file',
    icon: markRaw(FolderOpened),
  },
  {
    title: 'AI 功能',
    desc: 'AI 对话、OCR 识别与语音能力。',
    to: '/_sys/ai/chat',
    icon: markRaw(ChatDotRound),
  },
  {
    title: '数据库',
    desc: '数据概览、模型配置与待办事项。',
    to: '/_sys/database/overview',
    icon: markRaw(Document),
  },
  {
    title: '模板示例',
    desc: '布局容器、3D 场景等前端范例。',
    to: '/_sys/template/overview',
    icon: markRaw(Files),
  },
]
</script>
