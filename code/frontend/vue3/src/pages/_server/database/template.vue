<template>
  <div p-2 w-full>
    <!-- 搜索栏 -->
    <div class="search-bar">
      <el-input v-model="searchQuery" placeholder="输入模板名称搜索" clearable @clear="handleSearch" @keyup.enter="handleSearch"
        style="width: 300px">
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
      <el-button type="primary" @click="handleCreate" style="margin-left: 16px;">
        新增模板
      </el-button>
    </div>

    <!-- 数据表格 -->
    <el-table :data="tableData" v-loading="loading" border stripe w-full>
      <el-table-column v-for="column in tableColumns" :key="column.prop" :prop="column.prop" :label="column.label"
        :min-width="column.width">
        <!-- 日期 -->
        <template #default="{ row }">
          <!-- 日期 -->
          <span v-if="column.formatter">
            {{ column.formatter(row[column.prop]) }}
          </span>
          <!-- 按钮组 -->
          <template v-else-if="column.button_list">
            <template v-for="button in column.button_list">
              <el-button v-if="button.fuc_type == 'click'" size="small" :type="button.type" @click="button.fuc(row)"
                :key="button.label" plain>{{
                  button.label
                }}</el-button>
            </template>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <template v-for="column in tableColumns" :key="column.prop">
          <el-form-item v-if="column.edit" :prop="column.prop" :label="column.label">
            <!-- 组件 -->
            <el-input v-if="column.edit.component == 'el-input'" v-model="form[column.prop]"
              :type="column.edit.props?.type" :rows="column.edit.props?.rows" :placeholder="column.edit.placeholder" />
            <!-- 数值输入框 -->
            <el-input-number v-if="column.edit.component == 'el-input-number'" v-model="form[column.prop]"
              :min="column.edit.props?.min" :step="column.edit.props?.step" style="width: 100%" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            确认
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { createTemplate, deleteTemplate, updateTemplate, getTemplate, listTemplates } from '@/api/template'
import {
  // type InfiniteScrollParams,
  // type InfiniteScrollResponse,
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { Template, TemplateCreate, TemplateUpdate } from '@/types/template';
import { config, rules, formBase } from '@/types/template';
import {
  ElMessage, ElMessageBox, type FormInstance,
  // type FormRules
} from 'element-plus'

// 表格行
const tableColumns: any = ref(config.tableColumns);
// 搜索条件
const searchQuery = ref('')

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

// 表格数据
const tableData = ref<Template[]>([])
const total = ref(0)
const loading = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentTemplateId = ref<string | null>(null)

// 表单数据
// 深拷贝formBase
const form_copy = JSON.parse(JSON.stringify(formBase))
const form = reactive(form_copy)


// 对话框标题
const dialogTitle = computed(() => {
  return currentTemplateId.value ? '编辑模板' : '新增模板'
})

// // 日期格式化
// const formatDate = (dateString: string) => {
//   return new Date(dateString).toLocaleString()
// }

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    const params = {
      ...pagination.value,
      name: searchQuery.value || undefined // 空字符串不传
    }

    const response: PaginationResponse<Template> = await listTemplates(params)
    tableData.value = response.items
    total.value = response.total

    // 如果当前页无数据且不是第一页，则自动返回前一页
    if (response.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取模板列表失败:', error)
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
  currentTemplateId.value = null
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
const handleEdit = async (row: Template) => {
  try {
    resetForm()
    currentTemplateId.value = row.id

    // 获取模板详情
    const response = await getTemplate(row.id)
    const template = response

    // 填充表单数据
    form.name = template.name
    form.description = template.description || ''
    form.value = template.value

    dialogVisible.value = true
  } catch (error) {
    console.error('获取模板详情失败:', error)
    ElMessage.error('获取模板详情失败，请重试')
  }
}


// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentTemplateId.value) {
      // 更新模板
      const updateData: TemplateUpdate = {
        name: form.name,
        description: form.description,
        value: form.value
      }
      await updateTemplate(currentTemplateId.value, updateData)
      ElMessage.success('模板更新成功')
    } else {
      // 创建模板
      const createData: TemplateCreate = {
        name: form.name,
        description: form.description,
        value: form.value
      }
      await createTemplate(createData)
      ElMessage.success('模板创建成功')
    }

    dialogVisible.value = false
    fetchData() // 刷新数据
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentTemplateId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: Template) => {
  try {
    await ElMessageBox.confirm('确定要删除此模板吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })

    // 调用删除API
    await deleteTemplate(row.id)
    ElMessage.success('删除成功')

    // 检查是否需要调整分页
    if (tableData.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }

    fetchData() // 刷新数据
  } catch (error) {
    console.log('取消删除或删除失败')
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

<style scoped>
.template-container {
  padding: 20px;
}

.search-bar {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>