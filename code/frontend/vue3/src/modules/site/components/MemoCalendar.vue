<template>
  <!-- 备忘日历(年/月/周 tab 切换), 供博客展示页右上角等场景嵌入 -->
  <div class="flex flex-col rounded-xl border border-note bg-note-card shadow-note">
    <!-- 头部: 视图切换 + 周期导航 -->
    <div class="flex flex-wrap items-center gap-2 border-b border-note px-3 py-2">
      <el-radio-group v-model="view" size="small">
        <el-radio-button value="year">年</el-radio-button>
        <el-radio-button value="month">月</el-radio-button>
        <el-radio-button value="week">周</el-radio-button>
      </el-radio-group>

      <!-- 周期导航: 上一周期 / 今天 / 下一周期 -->
      <div class="ml-auto flex items-center gap-1">
        <el-button size="small" text :icon="ArrowLeft" @click="step(-1)" />
        <el-button size="small" text class="text-xs" @click="goToday">今天</el-button>
        <el-button size="small" text :icon="ArrowRight" @click="step(1)" />
      </div>

      <!-- 当前周期标题 -->
      <div class="order-first w-full text-center text-sm font-bold text-note md:order-none md:w-auto md:min-w-[130px]">
        {{ title }}
      </div>
    </div>

    <!-- 视图主体 -->
    <div v-loading="loading" class="min-h-[220px] p-3">
      <CalendarYear
        v-if="view === 'year'"
        :year="anchorYear"
        :memos-by-date="memosByDate"
        :today="todayKey"
        @day-click="openDay"
      />
      <CalendarMonth
        v-else-if="view === 'month'"
        :year="anchorYear"
        :month="anchorMonth"
        :memos-by-date="memosByDate"
        :today="todayKey"
        @day-click="openDay"
      />
      <CalendarWeek
        v-else
        :anchor="anchor"
        :memos-by-date="memosByDate"
        :today="todayKey"
        @day-click="openDay"
      />
    </div>

    <!-- 底部: 前往备忘管理(工作台备忘面板) -->
    <div class="border-t border-note px-3 py-1.5 text-right">
      <el-button size="small" text type="primary" @click="router.push('/site?tab=memo')">
        备忘管理 →
      </el-button>
    </div>
  </div>

  <!-- 当日备忘详情抽屉(手机按屏宽自适应, append-to-body 保证弹出层不被父容器裁剪) -->
  <el-drawer
    v-model="drawerVisible"
    :title="drawerTitle"
    :size="isMd ? '420px' : '92%'"
    append-to-body
  >
    <div class="space-y-3">
      <div
        v-for="memo in dayMemos"
        :key="memo.id"
        class="rounded-lg border border-note bg-note-soft/60 p-3"
      >
        <div class="flex items-center gap-2">
          <el-tag :type="statusTagType(memo.status)" size="small">{{ statusLabel(memo.status) }}</el-tag>
          <span class="text-xs text-note-sub">{{ formatTime(memo.start_at) }}</span>
          <!-- 完成/恢复 快捷切换 -->
          <el-button
            size="small"
            text
            :type="memo.status === 'done' ? 'warning' : 'success'"
            class="ml-auto"
            @click="toggleDayMemoStatus(memo)"
          >{{ memo.status === 'done' ? '恢复' : '完成' }}</el-button>
        </div>
        <h4 class="mt-1.5 text-sm font-bold text-note">{{ memo.name }}</h4>
        <p
          v-if="memo.value"
          class="mt-1 text-xs leading-5 text-note-sub whitespace-pre-wrap break-all"
        >{{ memo.value }}</p>
      </div>
      <el-empty v-if="dayMemos.length === 0" description="当日暂无备忘" :image-size="80" />
    </div>
    <template #footer>
      <div class="flex justify-between">
        <el-button type="primary" plain size="small" :icon="Plus" @click="openQuickCreate">
          新增备忘
        </el-button>
        <el-button size="small" text @click="router.push('/site?tab=memo')">
          前往备忘管理
        </el-button>
      </div>
    </template>
  </el-drawer>

  <!-- 快捷创建备忘(预填抽屉对应日期 09:00) -->
  <el-dialog v-model="createVisible" title="新增备忘" width="90%" class="max-w-[460px]!">
    <el-form :model="createForm" label-width="80px">
      <el-form-item label="标题" required>
        <el-input v-model="createForm.name" placeholder="请输入备忘标题" maxlength="100" />
      </el-form-item>
      <el-form-item label="备忘时间">
        <el-date-picker
          v-model="createForm.start_at"
          type="datetime"
          placeholder="选择日历展示时间"
          format="YYYY-MM-DD HH:mm"
          date-format="YYYY-MM-DD"
          time-format="HH:mm"
          class="w-full!"
        />
      </el-form-item>
      <el-form-item label="内容">
        <el-input
          v-model="createForm.value"
          type="textarea"
          :rows="4"
          placeholder="备忘全文(周视图日历将展示前200字摘录)"
          maxlength="2000"
        />
      </el-form-item>
      <el-form-item label="状态">
        <el-radio-group v-model="createForm.status">
          <el-radio-button value="todo">待办</el-radio-button>
          <el-radio-button value="done">完成</el-radio-button>
          <el-radio-button value="pause">暂停</el-radio-button>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible = false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="handleQuickCreate">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createTodolist, listMemosByRange, updateTodolist } from '../api/todolist'
import type { Todolist, TodoStatus } from '../types/todolist'
import {
  dateKey,
  groupByDate,
  viewRange,
  viewTitle,
  type CalendarView,
} from '../composables/useCalendar'
import CalendarYear from './calendar/CalendarYear.vue'
import CalendarMonth from './calendar/CalendarMonth.vue'
import CalendarWeek from './calendar/CalendarWeek.vue'
import { SysSettingStore } from '@/common/stores/sys'

const router = useRouter()

// 响应式断点(手机抽屉宽度自适应)
const sysSettingStore = SysSettingStore()
const isMd = computed(() => sysSettingStore.sysStyle.isMd)

/** 当前视图(缺省月视图) */
const view = ref<CalendarView>('month')
/** 视图锚点日期 */
const anchor = ref(new Date())

const anchorYear = computed(() => anchor.value.getFullYear())
const anchorMonth = computed(() => anchor.value.getMonth() + 1)
const todayKey = dateKey(new Date())

/** 当前周期标题 */
const title = computed(() => viewTitle(view.value, anchor.value))

/** 按日期键分组的备忘 */
const memosByDate = ref(new Map<string, Todolist[]>())
const loading = ref(false)

/** 拉取当前视图范围的备忘并按日分组 */
async function fetchMemos() {
  loading.value = true
  try {
    const [start, end] = viewRange(view.value, anchor.value)
    const items = await listMemosByRange(start, end)
    memosByDate.value = groupByDate(items)
  } catch (error) {
    console.error('获取备忘日历失败:', error)
    ElMessage.error('获取备忘日历失败，请重试')
  } finally {
    loading.value = false
  }
}

// 视图/锚点变化 → 重新拉取
watch([view, anchor], fetchMemos, { immediate: true })

/** 切换上/下一周期(年±1 / 月±1 / 周±7天) */
function step(dir: 1 | -1) {
  const next = new Date(anchor.value)
  if (view.value === 'year') {
    next.setFullYear(next.getFullYear() + dir)
  } else if (view.value === 'month') {
    // 先清零到1日再改月份, 避免大月31日跳到下月
    next.setDate(1)
    next.setMonth(next.getMonth() + dir)
  } else {
    next.setDate(next.getDate() + dir * 7)
  }
  anchor.value = next
}

/** 回到今天 */
function goToday() {
  anchor.value = new Date()
}

/** 当日详情抽屉 */
const drawerVisible = ref(false)
const drawerDateKey = ref('')
const drawerTitle = computed(() => `${drawerDateKey.value} 的备忘`)
const dayMemos = computed(() => memosByDate.value.get(drawerDateKey.value) ?? [])

function openDay(key: string) {
  drawerDateKey.value = key
  drawerVisible.value = true
}

// ---------- 快捷创建备忘(预填该日 09:00) ----------
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  name: '',
  value: '',
  start_at: new Date(),
  status: 'todo' as TodoStatus,
})

function openQuickCreate() {
  // 从日期键(YYYY-MM-DD)构造预填时间, 避免时区偏移
  const [y, m, d] = drawerDateKey.value.split('-').map(Number)
  createForm.name = ''
  createForm.value = ''
  createForm.start_at = new Date(y, m - 1, d, 9, 0, 0)
  createForm.status = 'todo'
  createVisible.value = true
}

async function handleQuickCreate() {
  if (!createForm.name.trim()) {
    ElMessage.warning('请输入备忘标题')
    return
  }
  creating.value = true
  try {
    await createTodolist({
      name: createForm.name.trim(),
      value: createForm.value,
      start_at: createForm.start_at.toISOString(),
      status: createForm.status,
    })
    ElMessage.success('备忘已创建')
    createVisible.value = false
    drawerVisible.value = false
    fetchMemos()
  } catch (error) {
    console.error('创建备忘失败:', error)
    ElMessage.error('创建失败，请重试')
  } finally {
    creating.value = false
  }
}

// ---------- 抽屉内完成/恢复快捷切换(本地更新, 不整页刷新) ----------
async function toggleDayMemoStatus(memo: Todolist) {
  const next: TodoStatus = memo.status === 'done' ? 'todo' : 'done'
  try {
    await updateTodolist(memo.id, { status: next })
    // 以新 Map 替换触发响应, 更新当日列表
    const list = memosByDate.value.get(drawerDateKey.value) ?? []
    const nextList = list.map((m) => (m.id === memo.id ? { ...m, status: next } : m))
    const nextMap = new Map(memosByDate.value)
    nextMap.set(drawerDateKey.value, nextList)
    memosByDate.value = nextMap
    ElMessage.success(next === 'done' ? '已完成' : '已恢复待办')
  } catch (error) {
    console.error('状态切换失败:', error)
    ElMessage.error('操作失败，请重试')
  }
}

const statusLabel = (s: TodoStatus) =>
  ({ todo: '待办', done: '完成', pause: '暂停' })[s] ?? s
const statusTagType = (s: TodoStatus) =>
  ({ todo: 'warning', done: 'success', pause: 'info' })[s] ?? 'info'

/** 备忘时间(HH:mm) */
const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
</script>
