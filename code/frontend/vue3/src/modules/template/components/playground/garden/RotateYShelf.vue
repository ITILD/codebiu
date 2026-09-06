<template>
  <!-- 旋转书架: 书脊朝前立在架上, 悬停时绕 Y 轴拉出, 露出与书脊垂直的封面 -->
  <div class="flex flex-col gap-4 lg:flex-row">
    <div class="bookcase flex-1 rounded-md border border-[var(--el-border-color-light)] bg-[#efe9d8] p-6">
      <div v-for="(row, ri) in shelves" :key="ri" class="mb-6">
        <!-- 一排书: preserve-3d 的书立在同一透视里 -->
        <div class="shelf-row flex items-end gap-1.5 px-2" :style="{ perspective: '900px' }">
          <div
            v-for="b in row"
            :key="b.title"
            class="book relative"
            :style="{ width: `${b.w}px`, height: `${b.h}px` }"
            tabindex="0"
          >
            <!-- 书脊(正面) -->
            <div class="book-spine absolute inset-0 flex items-center justify-center rounded-r-sm rounded-l-sm" :style="{ background: b.color }">
              <span class="spine-title text-xs font-semibold text-white/95">{{ b.title }}</span>
            </div>
            <!-- 封面(与书脊垂直, 平时侧对观众) -->
            <div class="book-cover absolute top-0 left-full flex h-full w-28 items-end rounded-r-md p-2" :style="{ background: `linear-gradient(135deg, ${b.color}, ${b.deep})` }">
              <span class="text-xs text-white/90">📖 {{ b.title }}</span>
            </div>
            <!-- 书页侧面(左侧白边) -->
            <div class="book-pages absolute top-0.5 -left-1 h-[calc(100%-4px)] w-1 rounded-l bg-[repeating-linear-gradient(90deg,#fff_0_1px,#ddd_1px_2px)]" />
          </div>
          <!-- 斜倚的书(装饰) -->
          <div class="book-slant relative h-24 w-8 self-end" :style="{ background: 'linear-gradient(180deg,#8a9a7b,#6f7f61)' }" />
        </div>
        <!-- 层板 -->
        <div class="h-2.5 rounded-sm bg-[#b0946a] shadow-[0_3px_0_#96794f]" />
      </div>
      <p class="text-center text-xs text-[#7a6f57]">悬停一本书 · 绕 Y 轴拉出看封面</p>
    </div>

    <!-- 说明 -->
    <div class="w-full shrink-0 space-y-1 lg:w-56">
      <p class="pt-1 text-xs leading-5 text-[var(--el-text-color-secondary)]">
        书 = preserve-3d 的容器: 书脊在 z=0 平面, 封面是 rotateY(90°) 后"折"进深度的平面;
        悬停时整本书 rotateY(-32°) 向观众转出 32°, 原本侧对的封面随之可见 —— 一本书由两张面拼成, 全靠变换而非图片。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// CSS 3D 书架(garden.bradwoods.io/notes/css/3d): preserve-3d + 平面折叠
/** 一本书 */
interface Book {
  title: string
  color: string
  deep: string
  w: number
  h: number
}

/** 两层书架(园艺书房) */
const shelves: Book[][] = [
  [
    { title: '堆肥指南', color: '#4a7c59', deep: '#33573f', w: 40, h: 150 },
    { title: '香草图鉴', color: '#6f9579', deep: '#4c6b55', w: 34, h: 138 },
    { title: '土壤学', color: '#8a6d3b', deep: '#63492a', w: 46, h: 156 },
    { title: '月令花事', color: '#b08a3e', deep: '#7d5f28', w: 36, h: 132 },
    { title: '苔藓志', color: '#5d7a52', deep: '#3f5638', w: 38, h: 144 },
  ],
  [
    { title: '雨水园', color: '#3f7a6e', deep: '#2a554c', w: 42, h: 148 },
    { title: '蜜蜂与花', color: '#c2872e', deep: '#8a5e1e', w: 36, h: 136 },
    { title: '老圃闲谈', color: '#7b6d8a', deep: '#544962', w: 40, h: 152 },
    { title: '温室建造', color: '#a8762e', deep: '#75511f', w: 48, h: 158 },
    { title: '种子保存', color: '#5f8a4a', deep: '#426033', w: 34, h: 130 },
  ],
]
</script>

<style scoped>
/* 书: 三维容器, 悬停/聚焦时拉出 */
.book {
  transform-style: preserve-3d;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
  cursor: pointer;
}
.book:hover,
.book:focus-visible {
  transform: rotateY(-32deg) translateZ(16px);
  outline: none;
}

/* 书脊: 竖排书名 */
.book-spine {
  backface-visibility: hidden;
  box-shadow: inset -3px 0 5px rgba(0, 0, 0, 0.25), inset 2px 0 3px rgba(255, 255, 255, 0.18);
}
.spine-title {
  writing-mode: vertical-rl;
  letter-spacing: 0.15em;
}

/* 封面: 折进深度; rotateY(90) 使其与书脊垂直 */
.book-cover {
  transform: rotateY(90deg);
  transform-origin: left center;
  box-shadow: inset -6px 0 12px rgba(0, 0, 0, 0.3);
}

/* 斜倚装饰书 */
.book-slant {
  transform: rotate(12deg) translateY(6px);
  border-radius: 3px 5px 2px 2px;
  box-shadow: -2px 2px 4px rgba(0, 0, 0, 0.2);
  margin-left: 0.75rem;
}
</style>
