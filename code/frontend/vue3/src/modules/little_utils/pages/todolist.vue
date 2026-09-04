<template>
  <div p-4 md:p-6 w-full>
    <!-- 统一搜索栏: 多字段筛选 -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      @search="handleSearch"
      @reset="handleSearch"
    >
      <template #actions>
        <el-button type="primary" @click="handleCreate">新增计划任务</el-button>
      </template>
    </TableSearchBar>

    <!-- 数据表格 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column
        v-for="column in tableColumns"
        :key="column.prop"
        :prop="column.prop"
        :label="column.label"
        :min-width="column.width"
        :sortable="column.prop === 'created_at' ? true : undefined"
        :show-overflow-tooltip="column.prop === 'name' || column.prop === 'description'"
      >
        <!-- 日期 -->
        <template #default="{ row }">
          <!-- 日期 -->
          <span v-if="column.formatter">
            {{ column.formatter(row[column.prop]) }}
          </span>
          <!-- 按钮组 -->
          <template v-else-if="column.button_list">
            <template v-for="button in column.button_list">
              <el-button
                v-if="button.fuc_type == 'click'"
                size="small"
                :type="button.type"
                @click="button.fuc(row)"
                :key="button.label"
                plain
                >{{ button.label }}</el-button
              >
            </template>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="total"
        layout="total, prev, pager, next"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[600px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <template v-for="column in tableColumns" :key="column.prop">
          <el-form-item v-if="column.edit" :prop="column.prop" :label="column.label">
            <!-- 组件 -->
            <el-input
              v-if="column.edit.component == 'el-input'"
              v-model="form[column.prop]"
              :type="column.edit.props?.type"
              :rows="column.edit.props?.rows"
              :placeholder="column.edit.placeholder"
            />
            <!-- 数值输入框 -->
            <el-input-number
              v-if="column.edit.component == 'el-input-number'"
              v-model="form[column.prop]"
              :min="column.edit.props?.min"
              :step="column.edit.props?.step"
              w-full
            />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting"> 确认 </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  createTodolist,
  deleteTodolist,
  updateTodolist,
  getTodolist,
  listTodolists,
} from '../api/todolist'
import {
  // type InfiniteScrollParams,
  // type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/common/types/common'
import type { Todolist, TodolistCreate, TodolistUpdate } from '../types/todolist'
import { config, rules, formBase } from '../types/todolist'
import type { SearchField } from '@/common/components/TableSearchBar.vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  // type FormRules
} from 'element-plus'

// 表格行
const tableColumns: any = ref(config.tableColumns)

// 搜索字段配置(名称/状态多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'name', label: '任务名称' },
  {
    prop: 'status', label: '状态', type: 'select', options: [
      { label: '待办', value: 'todo' },
      { label: '已完成', value: 'done' },
    ]
  },
]

// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  name: '',
  status: undefined,
})

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10,
})

// 表格数据
const tableData = ref<Todolist[]>([])
const total = ref(0)
const loading = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentTodolistId = ref<string | null>(null)

// 表单数据
// 深拷贝formBase
const form_copy = JSON.parse(JSON.stringify(formBase))
const form = reactive(form_copy)

// 对话框标题
const dialogTitle = computed(() => {
  return currentTodolistId.value ? '编辑计划任务' : '新增计划任务'
})

// // 日期格式化
// const formatDate = (dateString: string) => {
//   return new Date(dateString).toLocaleString()
// }

// 获取数据(携带多字段过滤参数)
const fetchData = async () => {
  try {
    loading.value = true
    const { name, status } = queryParams.value
    const params = {
      ...pagination.value,
      // 空值不传递, 由后端进行模糊/精确过滤
      name: name || undefined,
      status: status || undefined,
    }

    const response: PaginationResponse<Todolist> = await listTodolists(params)
    tableData.value = response.items
    total.value = response.total

    // 如果当前页无数据且不是第一页，则自动返回前一页
    if (response.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取计划任务列表失败:', error)
    ElMessage.error('获取数据失败，请重试')
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  pagination.value.page = 1 // 搜索时重置到第一页
  fetchData()
}

// 重置表单
const resetForm = () => {
  if (formRef.value) formRef.value.resetFields()
  currentTodolistId.value = null
  // 重置
  for (const key in form) {
    form[key] = formBase[key]
  }
}

// 打开创建对话框
const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = async (row: Todolist) => {
  try {
    resetForm()
    currentTodolistId.value = row.id

    // 获取计划任务详情
    const response = await getTodolist(row.id)
    const todolist = response

    // 填充表单数据
    form.name = todolist.name
    form.description = todolist.description || ''
    form.value = todolist.value

    dialogVisible.value = true
  } catch (error) {
    console.error('获取计划任务详情失败:', error)
    ElMessage.error('获取计划任务详情失败，请重试')
  }
}

// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentTodolistId.value) {
      // 更新计划任务
      const updateData: TodolistUpdate = {
        name: form.name,
        description: form.description,
        value: form.value,
      }
      await updateTodolist(currentTodolistId.value, updateData)
      ElMessage.success('计划任务更新成功')
    } else {
      // 创建计划任务
      const createData: TodolistCreate = {
        name: form.name,
        description: form.description,
        value: form.value,
      }
      await createTodolist(createData)
      ElMessage.success('计划任务创建成功')
    }

    dialogVisible.value = false
    fetchData() // 刷新数据
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentTodolistId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: Todolist) => {
  try {
    await ElMessageBox.confirm('确定要删除此计划任务吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })

    // 调用删除API
    await deleteTodolist(row.id)
    ElMessage.success('删除成功')

    // 检查是否需要调整分页
    if (tableData.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }

    fetchData() // 刷新数据
  } catch (error) {
    console.log('取消删除或删除失败:', error)
    ElMessage.error('删除失败，请重试')
  }
}

// 最后一个元素默认为操作按钮组
const button_list = tableColumns.value.at(-1)?.button_list
if (button_list) {
  button_list['edit'].fuc = handleEdit
  button_list['delete'].fuc = handleDelete
}

// 初始化加载数据
onMounted(() => {
  fetchData()
})
</script>
