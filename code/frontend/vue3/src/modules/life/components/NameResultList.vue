<template>
  <!-- 评定结果名字卡片栅格 -->
  <div>
    <!-- 空状态 -->
    <div v-if="!names.length" flex flex-col items-center justify-center py-10 text-note-sub>
      <div text-5xl mb-3>🍼</div>
      <div text-sm>还没有生成名字</div>
      <div text-xs mt-1>完善宝宝信息并点击"开始起名"试试</div>
    </div>

    <!-- 名字卡片 -->
    <div v-else grid grid-cols-1 sm:grid-cols-2 gap-3>
      <div
        v-for="(item, i) in names" :key="`${item.name}-${i}`"
        class="name-card note-transition rounded-xl border p-3.5 shadow-note"
        :class="isExpanded(i) ? 'border-note-green bg-note-soft' : 'border-note bg-note-card'"
        hover:shadow-note-hover hover:-translate-y-0.5
      >
        <!-- 名字行 + 评分 -->
        <div flex items-center gap-2>
          <span
            text-2xl font-bold text-note tracking-widest truncate
            style="font-family: var(--note-font-hand)"
          >{{ item.name }}</span>
          <!-- 综合评分(三才五格得分, 未启用三才时不显示) -->
          <span
            v-if="showSancai && item.sancai"
            ml-auto shrink-0 w-11 h-11 rounded-full flex flex-col items-center justify-center border
            :class="scoreClass(item.score)"
          >
            <span text-sm font-bold leading-none>{{ item.score }}</span>
            <span class="text-[10px]" leading-none mt-0.5>评分</span>
          </span>
        </div>

        <!-- 寓意(超两行截断, 点击展开/收起) -->
        <div
          v-if="item.meaning"
          mt-1.5 text-xs text-note-sub leading-relaxed cursor-pointer select-none
          :class="{ 'line-clamp-2': !isExpanded(i) }"
          :title="isExpanded(i) ? '收起' : '展开寓意'"
          @click="toggleExpand(i)"
        >
          {{ item.meaning }}
        </div>
        <!-- 展开指示(仅寓意被截断时显示) -->
        <div
          v-if="item.meaning && isTruncated(item) && !isExpanded(i)"
          text-right class="text-[10px]" text-note-green
        >
          点击展开寓意 ▾
        </div>

        <!-- 三才五格明细 -->
        <div v-if="showSancai && item.sancai" mt-2 pt-2 border-t border-dashed border-note>
          <div flex items-center gap-1.5 flex-wrap>
            <span class="text-[10px]" text-note-sub>五格</span>
            <span
              v-for="g in GRIDS" :key="g.key"
              class="text-[10px]" px-1.5 py-0.5 rounded
              :class="item.sancai.grid_lucks[g.label] === '吉' || item.sancai.grid_lucks[g.label] === '大吉'
                ? 'bg-note-tint text-note-green'
                : 'bg-note-card border border-dashed border-note text-note-sub'"
            >
              {{ g.label }}{{ item.sancai[g.key] }}·{{ item.sancai.grid_lucks[g.label] }}
            </span>
          </div>
          <div flex items-center gap-1.5 mt-1.5>
            <span class="text-[10px]" text-note-sub>三才</span>
            <span class="text-[10px]" px-1.5 py-0.5 rounded bg-note-tint text-note>{{ item.sancai.sancai }}</span>
            <span v-if="item.sancai.estimated_chars.length" class="text-[10px]" text-note-sub>
              笔画估计:{{ item.sancai.estimated_chars.join('') }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/** 起名结果列表: 程序评定后的名字卡片(寓意可展开 + 三才五格评分明细) */
import type { EvaluatedName } from '../types/baby_name'

const props = defineProps<{
  /** 评定后的名字列表(多轮"生成更多"累加) */
  names: EvaluatedName[]
  /** 是否展示三才五格明细(选了三才参考才展示) */
  showSancai?: boolean
}>()

/** 五格渲染配置(吉凶键 → 数值键, 固定顺序) */
const GRIDS: { label: string; key: 'tian_ge' | 'ren_ge' | 'di_ge' | 'wai_ge' | 'zong_ge' }[] = [
  { label: '天格', key: 'tian_ge' },
  { label: '人格', key: 'ren_ge' },
  { label: '地格', key: 'di_ge' },
  { label: '外格', key: 'wai_ge' },
  { label: '总格', key: 'zong_ge' },
]

/** 评分分级样式(≥85 优 / ≥70 良 / 其余平) */
const scoreClass = (score: number) => {
  if (score >= 85) return 'bg-note-tint text-note-green border-note-green font-bold'
  if (score >= 70) return 'bg-note-tint text-note border-note'
  return 'bg-note-card text-note-sub border-note'
}

// ==================== 寓意展开/收起 ====================
const expandedIdx = ref<Set<number>>(new Set())

const isExpanded = (i: number) => expandedIdx.value.has(i)

/** 寓意是否被两行截断(约 40 字符为两行阈值, 大于才提示展开) */
const isTruncated = (item: EvaluatedName) => item.meaning.length > 40

/** 切换某张卡片的寓意展开态 */
const toggleExpand = (i: number) => {
  const next = new Set(expandedIdx.value)
  if (next.has(i)) next.delete(i)
  else next.add(i)
  expandedIdx.value = next
}

/** 名单变化(新批次追加/清空)时重置展开态 */
watch(
  () => props.names.length,
  () => {
    expandedIdx.value = new Set()
  },
)
</script>

<style scoped>
/* 名字卡片渐入动画(新批次名字追加时依次浮现); 展开态描边/底色由模板条件 uno 类承载 */
.name-card {
  animation: card-fade-up 0.45s ease both;
}
@keyframes card-fade-up {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
