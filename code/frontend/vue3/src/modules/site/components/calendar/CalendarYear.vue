<template>
  <!-- 年视图: 12个月迷你月历, 每月下方列出备忘标题 -->
  <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
    <div
      v-for="monthDate in months"
      :key="monthDate.getMonth()"
      class="rounded-lg border border-note bg-note-soft/60 p-2"
    >
      <!-- 月份标题 + 当月备忘数 -->
      <div class="flex items-center justify-between mb-1 px-0.5">
        <span class="text-xs font-bold text-note">{{ monthDate.getMonth() + 1 }}月</span>
        <span
          v-if="monthCount(monthDate) > 0"
          class="text-[10px] text-note-sub"
        >{{ monthCount(monthDate) }}条</span>
      </div>

      <!-- 迷你日历网格 -->
      <div class="grid grid-cols-7 gap-y-0.5">
        <span
          v-for="w in WEEKDAYS"
          :key="`h${w}`"
          class="text-center text-[9px] text-note-sub/70"
        >{{ w }}</span>
        <template v-for="cell in monthCells(monthDate)" :key="cell.date.getTime()">
          <button
            v-if="cell.inMonth"
            type="button"
            class="relative mx-auto flex h-5 w-5 items-center justify-center rounded text-[10px] leading-none transition-colors"
            :class="[
              dateKey(cell.date) === today
                ? 'bg-note-green text-white font-bold'
                : 'text-note hover:bg-note-tint',
            ]"
            @click="emit('day-click', dateKey(cell.date))"
          >
            {{ cell.date.getDate() }}
            <!-- 有备忘的日期显示角标点 -->
            <!-- 角标点有意用 bg-white: today 格底为苔绿实底(bg-note-green), 白点才能与其形成对比; 白底格则用苔绿点 -->
            <i
              v-if="hasMemo(cell.date)"
              class="absolute bottom-0 h-1 w-1 rounded-full"
              :class="dateKey(cell.date) === today ? 'bg-white' : 'bg-note-green'"
            />
          </button>
          <span v-else class="h-5 w-5" />
        </template>
      </div>

      <!-- 当月备忘标题(最多3条) -->
      <div class="mt-1.5 space-y-0.5 min-h-[16px]">
        <button
          v-for="memo in monthMemos(monthDate).slice(0, 3)"
          :key="memo.id"
          type="button"
          class="block w-full truncate rounded px-1 py-0.5 text-left text-[10px] text-note-sub hover:bg-note-tint hover:text-note"
          :title="memo.name ?? ''"
          @click="emit('day-click', dateKey(new Date(memo.start_at)))"
        >
          · {{ memo.name }}
        </button>
        <div
          v-if="monthMemos(monthDate).length > 3"
          class="px-1 text-[10px] text-note-sub/70"
        >
          +{{ monthMemos(monthDate).length - 3 }} 更多
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Todolist } from '../../types/todolist'
import { dateKey, monthGrid, yearMonths } from '../../composables/useCalendar'

const props = defineProps<{
  /** 聚焦年份 */
  year: number
  /** 按日期键分组的备忘 */
  memosByDate: Map<string, Todolist[]>
  /** 今天日期键(高亮) */
  today: string
}>()

const emit = defineEmits<{ (e: 'day-click', dateKey: string): void }>()

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

const months = computed(() => yearMonths(props.year))

/** 某月全部备忘 */
function monthMemos(monthDate: Date): Todolist[] {
  const out: Todolist[] = []
  for (const cell of monthGrid(monthDate.getFullYear(), monthDate.getMonth() + 1)) {
    if (!cell.inMonth) continue
    const list = props.memosByDate.get(dateKey(cell.date))
    if (list) out.push(...list)
  }
  return out
}

const monthCount = (monthDate: Date) => monthMemos(monthDate).length
const hasMemo = (d: Date) => (props.memosByDate.get(dateKey(d))?.length ?? 0) > 0
const monthCells = (monthDate: Date) =>
  monthGrid(monthDate.getFullYear(), monthDate.getMonth() + 1)
</script>
