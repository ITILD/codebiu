<template>
  <!-- 周视图: 容器感知双布局 — 窄容器(侧栏/手机抽屉)为议程行列表, 宽容器为7列网格 -->
  <div ref="rootEl" class="w-full">
    <!-- 窄容器: 议程式行列表(日头在左, 备忘 chips 在右换行) -->
    <div v-if="compact" class="flex flex-col gap-1.5">
      <div
        v-for="day in days"
        :key="day.getTime()"
        class="flex items-start gap-2 rounded-lg border p-2 transition-colors"
        :class="[
          keyOf(day) === today
            ? 'border-note-green bg-note-tint/60'
            : 'border-note bg-note-soft/50',
        ]"
      >
        <!-- 日头: 周X + 日期 -->
        <button
          type="button"
          class="flex w-11 shrink-0 flex-col items-center rounded py-0.5 text-center hover:opacity-80"
          @click="emit('day-click', keyOf(day))"
        >
          <span
            class="text-[11px] font-bold"
            :class="keyOf(day) === today ? 'text-note-green' : 'text-note'"
          >周{{ WEEKDAY_LABELS[day.getDay() === 0 ? 6 : day.getDay() - 1] }}</span>
          <span class="text-[10px] text-note-sub">{{ keyOf(day).slice(5) }}</span>
        </button>

        <!-- 当日备忘 chips(仅标题, 换行排列) -->
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1">
          <button
            v-for="memo in memosOf(day).slice(0, 3)"
            :key="memo.id"
            type="button"
            class="flex max-w-full items-center gap-1 rounded-md bg-note-card px-1.5 py-1 shadow-note transition-transform hover:-translate-y-0.5"
            @click="emit('day-click', keyOf(day))"
          >
            <i
              class="h-1.5 w-1.5 shrink-0 rounded-full"
              :class="memo.status === 'done' ? 'bg-note-sub/40' : 'bg-note-green'"
            />
            <span
              class="max-w-[9em] truncate text-[11px] font-semibold"
              :class="memo.status === 'done' ? 'text-note-sub line-through' : 'text-note'"
            >{{ memo.name }}</span>
          </button>
          <button
            v-if="memosOf(day).length > 3"
            type="button"
            class="rounded-md px-1 py-1 text-[10px] text-note-green hover:underline"
            @click="emit('day-click', keyOf(day))"
          >+{{ memosOf(day).length - 3 }}条</button>
          <span
            v-if="memosOf(day).length === 0"
            class="rounded-md border border-dashed border-note px-2 py-1 text-[10px] text-note-sub/60"
          >无备忘</span>
        </div>
      </div>
    </div>

    <!-- 宽容器: 7天卡片列, 每日最多3条(标题 + 前60字摘录) -->
    <div v-else class="grid grid-cols-7 gap-2">
      <div
        v-for="day in days"
        :key="day.getTime()"
        class="flex flex-col rounded-lg border p-2 transition-colors"
        :class="[
          keyOf(day) === today
            ? 'border-note-green bg-note-tint/60'
            : 'border-note bg-note-soft/50',
        ]"
      >
        <!-- 日头: 周X + 日期 -->
        <button
          type="button"
          class="mb-1.5 flex items-baseline justify-between rounded px-0.5 text-left hover:opacity-80"
          @click="emit('day-click', keyOf(day))"
        >
          <span
            class="text-[11px] font-bold"
            :class="keyOf(day) === today ? 'text-note-green' : 'text-note'"
          >周{{ WEEKDAY_LABELS[day.getDay() === 0 ? 6 : day.getDay() - 1] }}</span>
          <span class="text-[10px] text-note-sub">{{ keyOf(day).slice(5) }}</span>
        </button>

        <!-- 当日备忘(标题 + 短摘录, 最多3条) -->
        <div class="space-y-1.5">
          <div
            v-for="memo in memosOf(day).slice(0, 3)"
            :key="memo.id"
            class="cursor-pointer rounded-md bg-note-card p-1.5 shadow-note transition-transform hover:-translate-y-0.5"
            @click="emit('day-click', keyOf(day))"
          >
            <div class="flex items-center gap-1">
              <span
                class="truncate text-[11px] font-semibold"
                :class="memo.status === 'done' ? 'text-note-sub line-through' : 'text-note'"
              >{{ memo.name }}</span>
              <i
                class="ml-auto h-1.5 w-1.5 shrink-0 rounded-full"
                :class="memo.status === 'done' ? 'bg-note-sub/40' : 'bg-note-green'"
              />
            </div>
            <p
              v-if="memo.value"
              class="mt-0.5 text-[10px] leading-4 text-note-sub line-clamp-2 break-all"
            >{{ excerpt(memo.value, 60) }}</p>
          </div>
          <!-- 更多指示 + 空日占位 -->
          <button
            v-if="memosOf(day).length > 3"
            type="button"
            class="w-full rounded-md text-center text-[10px] text-note-green hover:underline"
            @click="emit('day-click', keyOf(day))"
          >+{{ memosOf(day).length - 3 }}条更多</button>
          <div
            v-if="memosOf(day).length === 0"
            class="rounded-md border border-dashed border-note py-2 text-center text-[10px] text-note-sub/60"
          >无备忘</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useElementSize } from '@vueuse/core'
import type { Todolist } from '../../types/todolist'
import { dateKey, excerpt, weekDays } from '../../composables/useCalendar'

const props = defineProps<{
  /** 聚焦锚点(所在周任意一天) */
  anchor: Date
  /** 按日期键分组的备忘 */
  memosByDate: Map<string, Todolist[]>
  /** 今天日期键(高亮) */
  today: string
}>()

const emit = defineEmits<{ (e: 'day-click', dateKey: string): void }>()

const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']

const days = computed(() => weekDays(props.anchor))

const keyOf = (d: Date) => dateKey(d)
const memosOf = (d: Date) => props.memosByDate.get(keyOf(d)) ?? []

// 容器感知: 视口断点无法感知侧栏/抽屉等窄容器, 按实际宽度切换布局
// (首帧未测得宽度时按窄容器渲染, 本组件主要嵌入 360px 侧栏/手机抽屉)
const rootEl = ref<HTMLElement | null>(null)
const { width } = useElementSize(rootEl)
const compact = computed(() => width.value === 0 || width.value < 640)
</script>
