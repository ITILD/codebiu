<template>
  <!-- 月视图: 标准月历网格, 每日显示备忘标题(点击查看当日详情) -->
  <div>
    <!-- 星期表头 -->
    <div class="grid grid-cols-7 mb-1">
      <span
        v-for="w in WEEKDAYS"
        :key="w"
        class="text-center text-[10px] text-note-sub"
      >{{ w }}</span>
    </div>

    <!-- 日期网格 -->
    <div class="grid grid-cols-7 gap-0.5">
      <button
        v-for="cell in cells"
        :key="cell.date.getTime()"
        type="button"
        class="min-h-[52px] rounded-md border p-1 text-left align-top transition-colors"
        :class="[
          cell.inMonth ? 'border-note bg-note-soft/50' : 'border-transparent opacity-40',
          keyOf(cell) === today ? 'ring-1.5 ring-note-green' : 'hover:bg-note-tint',
        ]"
        @click="emit('day-click', keyOf(cell))"
      >
        <span
          class="text-[11px] font-semibold"
          :class="keyOf(cell) === today ? 'text-note-green' : 'text-note'"
        >{{ cell.date.getDate() }}</span>
        <!-- 当日备忘标题(最多2条, 溢出省略) -->
        <span
          v-for="memo in memosOf(cell).slice(0, 2)"
          :key="memo.id"
          class="mt-0.5 block truncate rounded-sm bg-note-green/15 px-0.5 text-[9px] leading-4 text-note-green"
          :class="{ 'line-through opacity-60': memo.status === 'done' }"
        >{{ memo.name }}</span>
        <span
          v-if="memosOf(cell).length > 2"
          class="block text-[9px] text-note-sub"
        >+{{ memosOf(cell).length - 2 }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Todolist } from '../../types/todolist'
import { dateKey, monthGrid, type CalendarCell } from '../../composables/useCalendar'

const props = defineProps<{
  /** 聚焦年 */
  year: number
  /** 聚焦月(1-12) */
  month: number
  /** 按日期键分组的备忘 */
  memosByDate: Map<string, Todolist[]>
  /** 今天日期键(高亮) */
  today: string
}>()

const emit = defineEmits<{ (e: 'day-click', dateKey: string): void }>()

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

const cells = computed(() => monthGrid(props.year, props.month))

const keyOf = (cell: CalendarCell) => dateKey(cell.date)
const memosOf = (cell: CalendarCell) => props.memosByDate.get(keyOf(cell)) ?? []
</script>
