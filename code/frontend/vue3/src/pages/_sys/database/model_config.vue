<template>
  <div p-2 w-full>
    <!-- 搜索栏 -->
    <div flex items-center mb-20px>
      <el-input v-model="searchQuery" placeholder="输入模型名称搜索" clearable @clear="handleSearch" @keyup.enter="handleSearch"
        w-300px>
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
      <el-button type="primary" @click="handleCreate" ml-16px>
        新增模型配置
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
          <!-- 枚举类型显示 -->
          <span v-else-if="column.enum">
            {{ column.enum[row[column.prop]] || row[column.prop] }}
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
          <!-- 默认显示 -->
          <span v-else>
            {{ column.prop === 'api_key' && row[column.prop] ? '******' : row[column.prop] }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div mt-20px flex justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :page-sizes="[10, 20, 50, 100]" :total="total" layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <template v-for="column in tableColumns" :key="column.prop">
          <el-form-item v-if="column.edit" :prop="column.prop" :label="column.label">
            <!-- 下拉选择 -->
            <el-select v-if="column.edit.component == 'el-select'" v-model="form[column.prop]" :placeholder="column.edit.placeholder" w-full>
              <el-option v-for="option in column.edit.options" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <!-- 文本输入框 -->
            <el-input v-else-if="column.edit.component == 'el-input'" v-model="form[column.prop]"
              :type="column.edit.props?.type" :rows="column.edit.props?.rows" :placeholder="column.edit.placeholder" />
            <!-- 数值输入框 -->
            <el-input-number v-else-if="column.edit.component == 'el-input-number'" v-model="form[column.prop]"
              :min="column.edit.props?.min" :max="column.edit.props?.max" :step="column.edit.props?.step" w-full />
            <!-- 开关 -->
            <el-switch v-else-if="column.edit.component == 'el-switch'" v-model="form[column.prop]" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <span mt-20px text-right>
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
import { Search } from '@element-plus/icons-vue'
import { createModelConfig, deleteModelConfig, updateModelConfig, getModelConfig, listModelConfigs } from '@/api/model_config'
import {
  type PaginationParams,
  type PaginationResponse,
} from '@/types/common';
import type { ModelConfig, ModelConfigCreate, ModelConfigUpdate } from '@/types/model_config';
import { config, rules, formBase } from '@/types/model_config';
import {
  ElMessage, ElMessageBox, type FormInstance,
} from 'element-plus'

// 表格行
const tableColumns = ref(config.tableColumns);
// 搜索条件
const searchQuery = ref('')

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

// 表格数据
const tableData = ref<ModelConfig[]>([])
const total = ref(0)
const loading = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentModelConfigId = ref<string | null>(null)

// 表单数据
// 深拷贝formBase
const form_copy = JSON.parse(JSON.stringify(formBase))
const form = reactive(form_copy)

// 对话框标题
const dialogTitle = computed(() => {
  return currentModelConfigId.value ? '编辑模型配置' : '新增模型配置'
})

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    const params = {
      ...pagination.value,
      model: searchQuery.value || undefined // 空字符串不传
    }

    const response: PaginationResponse<ModelConfig> = await listModelConfigs(params)
    tableData.value = response.items
    total.value = response.total

    // 如果当前页无数据且不是第一页，则自动返回前一页
    if (response.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取模型配置列表失败:', error)
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
  currentModelConfigId.value = null
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
const handleEdit = async (row: ModelConfig) => {
  try {
    resetForm()
    currentModelConfigId.value = row.id

    // 获取模型配置详情
    const response = await getModelConfig(row.id)
    const modelConfig = response

    // 填充表单数据
    form.model_type = modelConfig.model_type
    form.server_type = modelConfig.server_type
    form.model = modelConfig.model
    form.url = modelConfig.url || ''
    form.api_key = modelConfig.api_key || ''
    form.pay_in = modelConfig.pay_in || 0
    form.pay_out = modelConfig.pay_out || 0
    form.input_tokens = modelConfig.input_tokens || 8192
    form.out_tokens = modelConfig.out_tokens || 8192
    form.temperature = modelConfig.temperature || 0.7
    form.timeout = modelConfig.timeout || 60
    form.no_think = modelConfig.no_think || false

    dialogVisible.value = true
  } catch (error) {
    console.error('获取模型配置详情失败:', error)
    ElMessage.error('获取模型配置详情失败，请重试')
  }
}

// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentModelConfigId.value) {
      // 更新模型配置
      const updateData: ModelConfigUpdate = {
        model_type: form.model_type,
        server_type: form.server_type,
        model: form.model,
        url: form.url || undefined,
        api_key: form.api_key || undefined,
        pay_in: form.pay_in,
        pay_out: form.pay_out,
        input_tokens: form.input_tokens,
        out_tokens: form.out_tokens,
        temperature: form.temperature,
        timeout: form.timeout,
        no_think: form.no_think
      }
      await updateModelConfig(currentModelConfigId.value, updateData)
      ElMessage.success('模型配置更新成功')
    } else {
      // 创建模型配置
      const createData: ModelConfigCreate = {
        model_type: form.model_type,
        server_type: form.server_type,
        model: form.model,
        url: form.url || undefined,
        api_key: form.api_key || undefined,
        pay_in: form.pay_in,
        pay_out: form.pay_out,
        input_tokens: form.input_tokens,
        out_tokens: form.out_tokens,
        temperature: form.temperature,
        timeout: form.timeout,
        no_think: form.no_think
      }
      await createModelConfig(createData)
      ElMessage.success('模型配置创建成功')
    }

    dialogVisible.value = false
    fetchData() // 刷新数据
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentModelConfigId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: ModelConfig) => {
  try {
    await ElMessageBox.confirm('确定要删除此模型配置吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })

    // 调用删除API
    await deleteModelConfig(row.id)
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

<style scoped>
</style>