<template>
  <div p-4 md:p-6 w-full class="dict-manage-page">
    <!-- 页面标题 -->
    <div mb-4>
      <h2 text-lg font-bold text-note>字段表管理</h2>
      <p text-xs text-note-sub mt-1>
        🌿 左侧为字段类型(dict_type)，右侧为对应字段项(dict_item)，点击类型查看其字段项
      </p>
    </div>

    <div flex flex-col lg:flex-row gap-4>
      <!-- ############ 左侧: 字段类型列表 ############ -->
      <div w-full shrink-0 p-4 rounded-lg bg-note-card border-note shadow-note class="lg:w-2/5">
        <div mb-3 flex items-center justify-between>
          <h3 font-bold text-note>字段类型</h3>
          <el-button size="small" type="primary" @click="openTypeDialog()">新增类型</el-button>
        </div>

        <!-- 类型搜索(服务端多字段过滤) -->
        <TableSearchBar
          v-model="queryParams"
          :fields="searchFields"
          :collapse-count="2"
          @search="handleSearch"
          @reset="handleSearch"
        />

        <!-- 类型表格 -->
        <el-table :data="typeList" v-loading="typeLoading" highlight-current-row stripe
          size="small" @current-change="handleTypeSelect">
          <el-table-column prop="type_name" label="类型名称" min-width="100" show-overflow-tooltip />
          <el-table-column prop="type_code" label="类型编码" min-width="100" show-overflow-tooltip />
          <el-table-column label="状态" width="70" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" link @click.stop="openTypeDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" link @click.stop="handleDeleteType(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 类型分页 -->
        <div mt-3 flex justify-center>
          <el-pagination v-model:current-page="typePagination.page" v-model:page-size="typePagination.size"
            :total="typeTotal" layout="total, prev, pager, next" small
            @size-change="fetchTypes" @current-change="fetchTypes" />
        </div>
      </div>

      <!-- ############ 右侧: 字段项列表 ############ -->
      <div flex-1 min-w-0 p-4 rounded-lg bg-note-card border-note shadow-note>
        <div mb-3 flex flex-wrap items-center justify-between gap-2>
          <h3 font-bold text-note>
            字段项
            <el-tag v-if="currentType" size="small" class="ml-2">{{ currentType.type_name }}</el-tag>
          </h3>
          <el-button size="small" type="primary" :disabled="!currentType" @click="openItemDialog()">
            新增字段项
          </el-button>
        </div>

        <!-- 未选择类型提示 -->
        <el-empty v-if="!currentType" description="请先在左侧选择一个字段类型" :image-size="80" />
        <template v-else>
          <!-- 项表格 -->
          <el-table :data="itemList" v-loading="itemLoading" stripe size="small">
            <el-table-column prop="item_name" label="项名称" min-width="100" show-overflow-tooltip />
            <el-table-column prop="item_code" label="项编码" min-width="100" show-overflow-tooltip />
            <el-table-column prop="item_value" label="项值" min-width="100" show-overflow-tooltip />
            <el-table-column prop="sort_order" label="排序" width="70" align="center" />
            <el-table-column label="状态" width="70" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" min-width="120" show-overflow-tooltip />
            <!-- 操作列: 平板及以上固定右侧, 手机取消固定避免遮挡 -->
            <el-table-column label="操作" min-width="110" align="center" :fixed="isMd ? 'right' : false">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="openItemDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="handleDeleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 项分页 -->
          <div mt-3 flex justify-center>
            <el-pagination v-model:current-page="itemPagination.page" v-model:page-size="itemPagination.size"
              :total="itemTotal" layout="total, prev, pager, next" small
              @size-change="fetchItems" @current-change="fetchItems" />
          </div>
        </template>
      </div>
    </div>

    <!-- ############ 类型编辑对话框 ############ -->
    <el-dialog v-model="typeDialogVisible" :title="editingTypeId ? '编辑字段类型' : '新增字段类型'"
      width="90%" class="max-w-[520px]">
      <el-form :model="typeForm" :rules="typeRules" ref="typeFormRef" label-width="90px">
        <el-form-item label="类型名称" prop="type_name">
          <el-input v-model="typeForm.type_name" placeholder="例如: 性别" />
        </el-form-item>
        <el-form-item label="类型编码" prop="type_code">
          <el-input v-model="typeForm.type_code" placeholder="例如: gender" :disabled="!!editingTypeId" />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="typeForm.sort_order" :min="0" w-full />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="typeForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="typeForm.description" type="textarea" :rows="2" placeholder="类型用途描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="typeDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleTypeSubmit" :loading="typeSubmitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- ############ 字段项编辑对话框 ############ -->
    <el-dialog v-model="itemDialogVisible" :title="editingItemId ? '编辑字段项' : '新增字段项'"
      width="90%" class="max-w-[520px]">
      <el-form :model="itemForm" :rules="itemRules" ref="itemFormRef" label-width="90px">
        <el-form-item label="项名称" prop="item_name">
          <el-input v-model="itemForm.item_name" placeholder="例如: 男" />
        </el-form-item>
        <el-form-item label="项编码" prop="item_code">
          <el-input v-model="itemForm.item_code" placeholder="例如: male" />
        </el-form-item>
        <el-form-item label="项值" prop="item_value">
          <el-input v-model="itemForm.item_value" placeholder="存储值(可选), 例如: 1" />
        </el-form-item>
        <el-form-item label="排序" prop="sort_order">
          <el-input-number v-model="itemForm.sort_order" :min="0" w-full />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="itemForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="itemForm.description" type="textarea" :rows="2" placeholder="字段项描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="itemDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleItemSubmit" :loading="itemSubmitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import {
  createDictType, deleteDictType, listDictTypes, updateDictType,
  createDictItem, deleteDictItem, listDictItemsByType, updateDictItem,
} from '../api/dict'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import { SysSettingStore } from '@/common/stores/sys'
import type { PaginationParams } from '@/common/types/common'
import type { DictType, DictItem } from '../types/dict'

// 断点状态(操作列固定策略)
const sysSettingStore = SysSettingStore()
const isMd = computed(() => sysSettingStore.sysStyle.isMd)

// ################ 左侧: 字段类型 ################
// 搜索字段配置(关键字/状态多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'keyword', label: '关键字', placeholder: '名称/编码模糊搜索' },
  {
    prop: 'is_active', label: '状态', type: 'select', options: [
      { label: '启用', value: true },
      { label: '禁用', value: false },
    ]
  },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  keyword: '',
  is_active: undefined,
})

const typeLoading = ref(false)
const typeList = ref<DictType[]>([])
const typeTotal = ref(0)
const typePagination = ref<PaginationParams>({ page: 1, size: 10 })
// 当前选中的类型(高亮行)
const currentType = ref<DictType | null>(null)

// 类型对话框
const typeDialogVisible = ref(false)
const typeFormRef = ref<FormInstance>()
const typeSubmitting = ref(false)
const editingTypeId = ref<string | null>(null)
const typeFormBase = {
  type_name: '',
  type_code: '',
  description: '',
  sort_order: 0,
  is_active: true,
}
const typeForm = reactive({ ...typeFormBase })
const typeRules = {
  type_name: [{ required: true, message: '请输入类型名称', trigger: 'blur' }],
  type_code: [{ required: true, message: '请输入类型编码', trigger: 'blur' }],
}

// 前端过滤类型(名称/编码模糊匹配) -- 已改为服务端过滤

/** 获取字段类型列表(携带多字段过滤参数) */
const fetchTypes = async () => {
  try {
    typeLoading.value = true
    const { keyword, is_active } = queryParams.value
    const res = await listDictTypes({
      ...typePagination.value,
      keyword: (keyword as string) || undefined,
      is_active: (is_active as boolean | undefined) ?? undefined,
    })
    typeList.value = res.items
    typeTotal.value = res.total
    // 当前选中类型被删掉时清空选择
    if (currentType.value && !res.items.some(t => t.id === currentType.value!.id)) {
      currentType.value = null
      itemList.value = []
      itemTotal.value = 0
    }
  } catch (error) {
    console.error('获取字段类型失败:', error)
    ElMessage.error('获取字段类型失败')
  } finally {
    typeLoading.value = false
  }
}

/** 搜索/重置: 回到第一页后重新查询 */
const handleSearch = () => {
  typePagination.value.page = 1
  fetchTypes()
}

/** 选中类型行时加载右侧字段项 */
const handleTypeSelect = (row: DictType | null) => {
  currentType.value = row
  if (row) {
    itemPagination.value.page = 1
    fetchItems()
  }
}

/** 打开类型对话框(row 为空时新增) */
const openTypeDialog = (row?: DictType) => {
  editingTypeId.value = row?.id ?? null
  Object.assign(typeForm, {
    type_name: row?.type_name ?? '',
    type_code: row?.type_code ?? '',
    description: row?.description ?? '',
    sort_order: row?.sort_order ?? 0,
    is_active: row?.is_active ?? true,
  })
  typeDialogVisible.value = true
}

/** 提交类型表单(创建/更新) */
const handleTypeSubmit = async () => {
  if (!typeFormRef.value) return
  const valid = await typeFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    typeSubmitting.value = true
    const data = {
      type_name: typeForm.type_name,
      type_code: typeForm.type_code,
      description: typeForm.description || null,
      sort_order: typeForm.sort_order,
      is_active: typeForm.is_active,
    }
    if (editingTypeId.value) {
      await updateDictType(editingTypeId.value, data)
      ElMessage.success('类型更新成功')
    } else {
      await createDictType(data)
      ElMessage.success('类型创建成功')
    }
    typeDialogVisible.value = false
    fetchTypes()
  } catch (error) {
    console.error('保存字段类型失败:', error)
    ElMessage.error('保存字段类型失败')
  } finally {
    typeSubmitting.value = false
  }
}

/** 删除类型(需二次确认) */
const handleDeleteType = async (row: DictType) => {
  try {
    await ElMessageBox.confirm(
      `确定删除类型「${row.type_name}」吗？其下字段项仍保留在数据库中。`,
      '警告', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteDictType(row.id)
    ElMessage.success('删除成功')
    fetchTypes()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    console.error('删除字段类型失败:', error)
    ElMessage.error('删除字段类型失败')
  }
}

// ################ 右侧: 字段项 ################
const itemLoading = ref(false)
const itemList = ref<DictItem[]>([])
const itemTotal = ref(0)
const itemPagination = ref<PaginationParams>({ page: 1, size: 10 })

// 项对话框
const itemDialogVisible = ref(false)
const itemFormRef = ref<FormInstance>()
const itemSubmitting = ref(false)
const editingItemId = ref<string | null>(null)
const itemFormBase = {
  item_name: '',
  item_code: '',
  item_value: '',
  description: '',
  sort_order: 0,
  is_active: true,
}
const itemForm = reactive({ ...itemFormBase })
const itemRules = {
  item_name: [{ required: true, message: '请输入项名称', trigger: 'blur' }],
  item_code: [{ required: true, message: '请输入项编码', trigger: 'blur' }],
}

/** 获取当前类型下的字段项列表(按类型编码全量查询后前端分页) */
const fetchItems = async () => {
  if (!currentType.value) return
  try {
    itemLoading.value = true
    const all = await listDictItemsByType(currentType.value.type_code)
    itemTotal.value = all.length
    // 排序字段按 sort_order 升序
    all.sort((a, b) => a.sort_order - b.sort_order)
    const { page, size } = itemPagination.value
    itemList.value = all.slice((page - 1) * size, page * size)
  } catch (error) {
    console.error('获取字段项失败:', error)
    ElMessage.error('获取字段项失败')
  } finally {
    itemLoading.value = false
  }
}

/** 打开项对话框(row 为空时新增) */
const openItemDialog = (row?: DictItem) => {
  editingItemId.value = row?.id ?? null
  Object.assign(itemForm, {
    item_name: row?.item_name ?? '',
    item_code: row?.item_code ?? '',
    item_value: row?.item_value ?? '',
    description: row?.description ?? '',
    sort_order: row?.sort_order ?? 0,
    is_active: row?.is_active ?? true,
  })
  itemDialogVisible.value = true
}

/** 提交项表单(创建/更新) */
const handleItemSubmit = async () => {
  if (!itemFormRef.value || !currentType.value) return
  const valid = await itemFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    itemSubmitting.value = true
    const data = {
      dict_type_id: currentType.value.id,
      item_name: itemForm.item_name,
      item_code: itemForm.item_code,
      item_value: itemForm.item_value || null,
      description: itemForm.description || null,
      sort_order: itemForm.sort_order,
      is_active: itemForm.is_active,
    }
    if (editingItemId.value) {
      await updateDictItem(editingItemId.value, data)
      ElMessage.success('字段项更新成功')
    } else {
      await createDictItem(data)
      ElMessage.success('字段项创建成功')
    }
    itemDialogVisible.value = false
    fetchItems()
  } catch (error) {
    console.error('保存字段项失败:', error)
    ElMessage.error('保存字段项失败')
  } finally {
    itemSubmitting.value = false
  }
}

/** 删除字段项(需二次确认) */
const handleDeleteItem = async (row: DictItem) => {
  try {
    await ElMessageBox.confirm(
      `确定删除字段项「${row.item_name}」吗？此操作不可恢复。`,
      '警告', { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteDictItem(row.id)
    ElMessage.success('删除成功')
    // 当前页删空时自动回退一页
    if (itemList.value.length === 1 && itemPagination.value.page > 1) {
      itemPagination.value.page -= 1
    }
    fetchItems()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    console.error('删除字段项失败:', error)
    ElMessage.error('删除字段项失败')
  }
}

// 初始化
onMounted(() => {
  fetchTypes()
})
</script>
