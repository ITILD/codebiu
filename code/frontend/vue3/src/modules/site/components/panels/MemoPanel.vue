<template>
  <div class="w-full">
    <!-- 搜索栏: 名称/状态过滤 + 新增入口 -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      @search="handleSearch"
      @reset="handleSearch"
    >
      <template #actions>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增备忘</el-button>
      </template>
    </TableSearchBar>

    <!-- 备忘表格 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column prop="name" label="标题" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span :class="{ 'line-through text-note-sub': row.status === 'done' }">
            {{ row.name }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="内容" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ excerpt(row.value, 60) || '—' }}</template>
      </el-table-column>
      <el-table-column label="备忘时间" min-width="160">
        <template #default="{ row }">{{ formatDateTime(row.start_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" min-width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="220" :fixed="isMd ? 'right' : false">
        <template #default="{ row }">
          <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            :type="row.status === 'done' ? 'warning' : 'success'"
            plain
            @click="toggleDone(row)"
          >{{ row.status === 'done' ? '恢复' : '完成' }}</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div class="mt-4 flex flex-wrap justify-center sm:justify-end">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </div>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="currentId ? '编辑备忘' : '新增备忘'" width="90%" class="max-w-[560px]!">
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.name" placeholder="请输入备忘标题" maxlength="100" />
        </el-form-item>
        <el-form-item label="备忘时间">
          <el-date-picker
            v-model="form.start_at"
            type="datetime"
            placeholder="选择日历展示时间"
            format="YYYY-MM-DD HH:mm"
            date-format="YYYY-MM-DD"
            time-format="HH:mm"
            class="w-full!"
          />
          <div class="w-full mt-1 text-xs text-note-sub">备忘将按此时间显示在博客展示页的日历中</div>
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            v-model="form.value"
            type="textarea"
            :rows="5"
            placeholder="备忘全文(周视图日历将展示前200字摘录)"
            maxlength="2000"
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" placeholder="补充描述(可选)" maxlength="500" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio-button value="todo">待办</el-radio-button>
            <el-radio-button value="done">完成</el-radio-button>
            <el-radio-button value="pause">暂停</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createTodolist, deleteTodolist, listTodolists, updateTodolist } from '../../api/todolist'
import type { Todolist, TodoStatus } from '../../types/todolist'
import { excerpt } from '../../composables/useCalendar'
import type { SearchField } from '@/common/components/TableSearchBar.vue'
import { SysSettingStore } from '@/common/stores/sys'

// 响应式断点(md 以下走移动端布局)
const sysSettingStore = SysSettingStore()
const isMd = computed(() => sysSettingStore.sysStyle.isMd)

// 搜索字段(名称/状态)
const searchFields: SearchField[] = [
  { prop: 'name', label: '标题' },
  {
    prop: 'status', label: '状态', type: 'select', options: [
      { label: '待办', value: 'todo' },
      { label: '完成', value: 'done' },
      { label: '暂停', value: 'pause' },
    ],
  },
]

const queryParams = ref<Record<string, unknown>>({ name: '', status: undefined })
const pagination = ref({ page: 1, size: 10 })

const tableData = ref<Todolist[]>([])
const total = ref(0)
const loading = ref(false)

// 获取备忘列表(携带过滤参数)
async function fetchData() {
  loading.value = true
  try {
    const { name, status } = queryParams.value
    const resp = await listTodolists({
      ...pagination.value,
      name: (name as string) || undefined,
      status: (status as string) || undefined,
    })
    tableData.value = resp.items
    total.value = resp.total
    // 当前页无数据且非第一页时回退一页
    if (resp.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取备忘列表失败:', error)
    ElMessage.error('获取备忘列表失败，请重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.value.page = 1
  fetchData()
}

// 编辑对话框状态
const dialogVisible = ref(false)
const currentId = ref<string | null>(null)
const submitting = ref(false)

const form = reactive({
  name: '',
  value: '',
  description: '',
  start_at: new Date(),
  status: 'todo' as TodoStatus,
})

function resetForm() {
  currentId.value = null
  form.name = ''
  form.value = ''
  form.description = ''
  form.start_at = new Date()
  form.status = 'todo'
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

async function openEdit(row: Todolist) {
  resetForm()
  currentId.value = row.id
  form.name = row.name ?? ''
  form.value = row.value ?? ''
  form.description = row.description ?? ''
  form.start_at = new Date(row.start_at)
  form.status = row.status
  dialogVisible.value = true
}

// 保存(创建或更新)
async function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入备忘标题')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      value: form.value,
      description: form.description.trim() || null,
      start_at: form.start_at.toISOString(),
      status: form.status,
    }
    if (currentId.value) {
      await updateTodolist(currentId.value, payload)
      ElMessage.success('备忘已更新')
    } else {
      await createTodolist(payload)
      ElMessage.success('备忘已创建')
    }
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('保存备忘失败:', error)
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// 完成/恢复 快捷切换
async function toggleDone(row: Todolist) {
  const next: TodoStatus = row.status === 'done' ? 'todo' : 'done'
  try {
    await updateTodolist(row.id, { status: next })
    row.status = next
    ElMessage.success(next === 'done' ? '已完成' : '已恢复待办')
  } catch (error) {
    console.error('状态切换失败:', error)
    ElMessage.error('操作失败，请重试')
  }
}

// 删除
async function handleDelete(row: Todolist) {
  try {
    await ElMessageBox.confirm(`确定删除备忘「${row.name}」吗？`, '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    await deleteTodolist(row.id)
    ElMessage.success('删除成功')
    if (tableData.value.length === 1 && pagination.value.page > 1) pagination.value.page -= 1
    fetchData()
  } catch {
    // 用户取消
  }
}

const statusLabel = (s: TodoStatus) => ({ todo: '待办', done: '完成', pause: '暂停' })[s] ?? s
const statusTagType = (s: TodoStatus) =>
  ({ todo: 'warning', done: 'success', pause: 'info' })[s] ?? 'info'
const formatDateTime = (v: string) => new Date(v).toLocaleString('zh-CN')

onMounted(fetchData)
</script>
