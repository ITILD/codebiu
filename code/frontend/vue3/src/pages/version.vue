<template>
  <!-- 版本信息页(独立页: 需登录、无侧边栏) —— 系统介绍 + 按时间线滚动的逐版本记录 -->
  <div page-shell>
    <div class="mx-auto max-w-4xl">
      <!-- ===== Hero: 系统介绍(项目名 + 当前版本 + 简介) ===== -->
      <section
        relative rounded-note-lg border-note bg-note-gradient shadow-note p-6 md:p-10
      >
        <div class="note-age-stain" absolute inset-0 pointer-events-none rounded-note-lg overflow-hidden />
        <div relative z-10>
          <div flex flex-wrap items-center gap-3>
            <h1 flex items-center font-serif text-3xl md:text-4xl font-bold text-note-green class="note-etch">
              {{ projectIntro.name }}
              <span class="note-seal ml-3" title="版本信息">版</span>
            </h1>
            <!-- 当前版本号: vite 打包时从 package.json 注入 -->
            <span px-3 py-1 rounded-full bg-note-tint text-sm text-note-green border border-dashed border-note-green>
              当前版本 v{{ appVersion }}
            </span>
          </div>

          <p font-hand text-lg md:text-xl text-note mt-3>{{ projectIntro.tagline }}</p>
          <p text-sm md:text-base text-note-sub leading-relaxed mt-2 max-w-2xl>
            {{ projectIntro.description }}
          </p>

          <!-- 统计条 -->
          <div flex flex-wrap items-center gap-x-5 gap-y-1 mt-4 text-xs md:text-sm text-note-sub>
            <span>共 {{ versions.length }} 个版本</span>
            <span class="note-dashed-divider" border-t w-8 />
            <span>2025-11 起按月迭代</span>
            <span class="note-dashed-divider" border-t w-8 />
            <span>相邻版本最短间隔一周</span>
          </div>
        </div>
      </section>

      <!-- ===== 主要功能列表 ===== -->
      <section mt-8>
        <div flex items-center gap-2 mb-4>
          <h2 font-serif text-xl md:text-2xl font-semibold text-note class="note-etch">主要功能</h2>
          <hr class="note-line-fade flex-1" />
        </div>
        <div grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4>
          <div
            v-for="feature in mainFeatures"
            :key="feature.title"
            class="note-glow-hover note-transition"
            bg-note-card rounded-note-md shadow-note p-4
          >
            <div flex items-center gap-2>
              <el-icon text-note-green text-lg>
                <component :is="featureIcons[feature.icon]" />
              </el-icon>
              <span font-medium text-note>{{ feature.title }}</span>
            </div>
            <p text-sm text-note-sub leading-relaxed mt-2>{{ feature.desc }}</p>
          </div>
        </div>
      </section>

      <!-- ===== 版本时间线(最新在前, 无限滚动分批渲染) ===== -->
      <section mt-10>
        <div flex items-center gap-2 mb-4>
          <h2 font-serif text-xl md:text-2xl font-semibold text-note class="note-etch">版本时间线</h2>
          <hr class="note-line-fade flex-1" />
        </div>

        <div relative>
          <!-- 时间线纵轴 -->
          <div class="absolute left-[7px] top-2 bottom-2 w-[2px] rounded-full" bg-note />

          <template v-for="(node, idx) in timelineNodes" :key="idx">
            <!-- 年份标记 -->
            <div v-if="node.type === 'year'" relative py-2 class="pl-8">
              <span class="absolute left-0 top-1/2 -translate-y-1/2 w-4 h-4 flex items-center justify-center">
                <span w-2.5 h-2.5 rounded-full bg-note-green shadow-note />
              </span>
              <span class="note-sticker-tag">{{ node.year }} 年</span>
            </div>

            <!-- 版本节点卡片 -->
            <article v-else relative pb-6 class="pl-8">
              <!-- 节点圆点: 开发中版本带呼吸点 -->
              <span
                absolute left-0 top-2 w-4 h-4 rounded-full border-2 border-note-green flex items-center justify-center
                :class="node.record.status === 'dev' ? 'bg-note-tint' : 'bg-note-card'"
              >
                <span
                  w-1.5 h-1.5 rounded-full bg-note-green
                  :class="node.record.status === 'dev' ? 'animate-pulse' : 'opacity-60'"
                />
              </span>

              <div class="note-glow-hover note-transition" bg-note-card rounded-note-md shadow-note p-4 md:p-5>
                <!-- 版本头: 版本号 + 主题 + 状态 + 周期 -->
                <div flex flex-wrap items-center gap-x-2 gap-y-1>
                  <span text-lg md:text-xl font-bold text-note-green>{{ node.record.version }}</span>
                  <span text-base font-medium text-note>{{ node.record.name }}</span>
                  <span v-if="node.record.status === 'dev'" class="note-sticker-tag">开发中</span>
                  <span ml-auto text-xs text-note-sub>{{ node.record.period }}</span>
                </div>

                <p text-sm text-note-sub mt-2>{{ node.record.summary }}</p>

                <!-- 亮点标签 -->
                <div flex flex-wrap gap-1.5 mt-2>
                  <span v-for="tag in node.record.tags" :key="tag" class="note-sticker-tag">{{ tag }}</span>
                </div>

                <!-- 功能明细: 桌面双列(大厂发布说明排版) -->
                <ul grid gap-x-6 gap-y-2 mt-3 class="sm:grid-cols-2">
                  <li v-for="feat in node.record.features" :key="feat.title" flex gap-2>
                    <span class="mt-[7px]" w-1.5 h-1.5 rounded-full bg-note-green shrink-0 />
                    <p text-sm leading-6 class="min-w-0">
                      <span font-medium text-note>{{ feat.title }}</span>
                      <span text-note-sub> — {{ feat.desc }}</span>
                    </p>
                  </li>
                </ul>
              </div>
            </article>
          </template>

          <!-- 无限滚动哨兵: 进入视口即追加下一批版本卡片 -->
          <div ref="sentinelRef" relative py-2 text-sm text-note-sub class="pl-8">
            <span v-if="!allLoaded">正在载入更早的版本…</span>
            <span v-else>已展示全部 {{ versions.length }} 个版本，回到项目起点。</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { markRaw, computed, ref } from 'vue'
import { useIntersectionObserver } from '@vueuse/core'
import { Compass, Files, Lock, MagicStick, Search, SetUp } from '@element-plus/icons-vue'
import { projectIntro, mainFeatures, versions } from '@/app/config/versions'
import type { VersionRecord } from '@/app/config/versions'

// 当前构建版本号: vite 打包时从 package.json 注入(模板中使用需先在 script 取值)
const appVersion = __APP_VERSION__

// ---- 主要功能图标: 数据源存图标名, 此处映射为组件 ----
const featureIcons: Record<string, unknown> = {
  Lock: markRaw(Lock),
  MagicStick: markRaw(MagicStick),
  Files: markRaw(Files),
  Search: markRaw(Search),
  Compass: markRaw(Compass),
  SetUp: markRaw(SetUp),
}

// ---- 时间线无限滚动: 分批挂载版本卡片, 避免一次性渲染全部条目 ----
const INITIAL_COUNT = 4 // 首屏渲染条数
const CHUNK_SIZE = 3 // 触底后每批追加条数
const visibleCount = ref(Math.min(INITIAL_COUNT, versions.length))
const allLoaded = computed(() => visibleCount.value >= versions.length)
const sentinelRef = ref<HTMLElement | null>(null)

const { stop } = useIntersectionObserver(
  sentinelRef,
  ([entry]) => {
    if (!entry?.isIntersecting) return
    // 全部载入后停止观察, 避免空转回调
    if (allLoaded.value) {
      stop()
      return
    }
    visibleCount.value = Math.min(visibleCount.value + CHUNK_SIZE, versions.length)
  },
  // 提前预加载: 哨兵接近视口底部前即追加, 滚动不中断
  { rootMargin: '480px 0px' },
)

// ---- 渲染序列: 年份变化处插入年份标记节点 ----
type TimelineNode = { type: 'year'; year: string } | { type: 'version'; record: VersionRecord }
const timelineNodes = computed<TimelineNode[]>(() => {
  const nodes: TimelineNode[] = []
  let lastYear = ''
  for (const record of versions.slice(0, visibleCount.value)) {
    const year = record.period.slice(0, 4)
    if (year !== lastYear) {
      nodes.push({ type: 'year', year })
      lastYear = year
    }
    nodes.push({ type: 'version', record })
  }
  return nodes
})
</script>
