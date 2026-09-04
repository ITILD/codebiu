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
        <el-button type="primary" @click="handleCreate">新增角色</el-button>
      </template>
    </TableSearchBar>

    <!-- 数据表格 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column prop="name" label="角色名称" min-width="120" show-overflow-tooltip />
      <el-table-column prop="role_key" label="权限字符" min-width="120" show-overflow-tooltip />
      <el-table-column prop="sort" label="显示顺序" min-width="100" sortable />
      <el-table-column label="数据权限范围" min-width="160">
        <template #default="{ row }">
          {{ getDataScopeLabel(row.data_scope) }}
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="100">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" disabled :active-text="row.is_active ? '启用' : '禁用'" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="180" sortable />
      <el-table-column label="操作" min-width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="success" plain @click="handlePermission(row)">分配权限</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[600px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="角色名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="权限字符" prop="role_key">
          <el-input v-model="form.role_key" placeholder="例如：admin、editor" />
        </el-form-item>
        <el-form-item label="显示顺序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" />
        </el-form-item>
        <el-form-item label="数据权限范围" prop="data_scope">
          <el-select v-model="form.data_scope" placeholder="请选择数据权限范围">
            <el-option v-for="item in dataScopeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入角色描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 分配权限对话框(模块声明树,勾选按钮级权限码) -->
    <el-dialog v-model="permDialogVisible" title="分配权限" width="90%" class="max-w-[700px]">
      <el-alert type="info" :closable="false" mb-3
        title="勾选权限树节点为角色授权；模块预设的通配策略(如模块管理员角色)不受影响" />
      <el-tree ref="treeRef" :data="permTreeData" show-checkbox node-key="code"
        :props="{ label: 'name', children: 'children' }" v-loading="permLoading" />
      <template #footer>
        <span>
          <el-button @click="permDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handlePermSubmit" :loading="permSubmitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { createRole, deleteRole, getRole, listRoles, updateRole } from '../api/role'
import { getModuleTree, getRolePermCodes, syncRolePermissions } from '../api/casbin'
import type { ModulePermNode } from '../api/casbin'
import type { PaginationParams, PaginationResponse } from '@/common/types/common'
import type { Role, RoleCreate, RoleUpdate } from '../types/role'
import { dataScopeOptions } from '../types/role'
import type { SearchField } from '@/common/components/TableSearchBar.vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// 搜索字段配置(名称/权限字符/状态多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'name', label: '角色名称' },
  { prop: 'role_key', label: '权限字符' },
  {
    prop: 'is_active', label: '状态', type: 'select', options: [
      { label: '启用', value: true },
      { label: '禁用', value: false },
    ]
  },
]

// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  name: '',
  role_key: '',
  is_active: undefined,
})

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

// 表格数据
const tableData = ref<Role[]>([])
const total = ref(0)
const loading = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentRoleId = ref<string | null>(null)

// 表单基础数据
const formBase: Record<string, any> = {
  name: '',
  role_key: '',
  description: '',
  sort: 0,
  data_scope: '1',
  is_active: true
}
const form_copy = JSON.parse(JSON.stringify(formBase))
const form = reactive(form_copy)

// 表单校验规则
const rules = {
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
  role_key: [{ required: true, message: '请输入权限字符', trigger: 'blur' }]
}

// 对话框标题
const dialogTitle = computed(() => {
  return currentRoleId.value ? '编辑角色' : '新增角色'
})

// 数据权限范围标签
const getDataScopeLabel = (value: string) => {
  return dataScopeOptions.find(o => o.value === value)?.label || value
}

// 分配权限相关
const permDialogVisible = ref(false)
const permLoading = ref(false)
const permSubmitting = ref(false)
const permTreeData = ref<ModulePermNode[]>([])
const currentRoleForPerm = ref<Role | null>(null)
const treeRef = ref()

// 获取数据(携带多字段过滤参数)
const fetchData = async () => {
  try {
    loading.value = true
    const { name, role_key, is_active } = queryParams.value
    const params = {
      ...pagination.value,
      // 空值不传递, 由后端进行模糊/精确过滤
      name: name || undefined,
      role_key: role_key || undefined,
      is_active: is_active ?? undefined,
    }
    const response: PaginationResponse<Role> = await listRoles(params)
    tableData.value = response.items
    total.value = response.total

    // 如果当前页无数据且不是第一页，则自动返回前一页
    if (response.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取角色列表失败:', error)
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
  currentRoleId.value = null
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
const handleEdit = async (row: Role) => {
  try {
    resetForm()
    currentRoleId.value = row.id

    // 获取角色详情
    const role = await getRole(row.id)

    // 填充表单数据
    form.name = role.name
    form.role_key = role.role_key
    form.description = role.description || ''
    form.sort = role.sort
    form.data_scope = role.data_scope
    form.is_active = role.is_active

    dialogVisible.value = true
  } catch (error) {
    console.error('获取角色详情失败:', error)
    ElMessage.error('获取角色详情失败，请重试')
  }
}

// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentRoleId.value) {
      // 更新角色
      const updateData: RoleUpdate = {
        name: form.name,
        role_key: form.role_key,
        description: form.description,
        sort: form.sort,
        data_scope: form.data_scope,
        is_active: form.is_active
      }
      await updateRole(currentRoleId.value, updateData)
      ElMessage.success('角色更新成功')
    } else {
      // 创建角色
      const createData: RoleCreate = {
        name: form.name,
        role_key: form.role_key,
        description: form.description,
        sort: form.sort,
        data_scope: form.data_scope,
        is_active: form.is_active
      }
      await createRole(createData)
      ElMessage.success('角色创建成功')
    }

    dialogVisible.value = false
    fetchData() // 刷新数据
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentRoleId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: Role) => {
  try {
    await ElMessageBox.confirm('确定要删除此角色吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })

    // 调用删除API
    await deleteRole(row.id)
    ElMessage.success('删除成功')

    // 检查是否需要调整分页
    if (tableData.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }

    fetchData() // 刷新数据
  } catch (error) {
    // 用户取消删除，不提示错误
    if (error === 'cancel' || error === 'close') return
    console.error('删除失败:', error)
    ElMessage.error('删除失败，请重试')
  }
}

// 打开分配权限对话框(对接模块声明树 + 角色节点权限码回显)
const handlePermission = async (row: Role) => {
  currentRoleForPerm.value = row
  permDialogVisible.value = true
  permLoading.value = true
  try {
    // 并行加载模块声明树(仅首次加载,后续复用)与角色已有权限码
    const treePromise =
      permTreeData.value.length === 0
        ? getModuleTree().then((res) => (permTreeData.value = res.data))
        : Promise.resolve()
    const codesPromise = getRolePermCodes(row.role_key)
    const [, codesRes] = await Promise.all([treePromise, codesPromise])
    // 等待树渲染后回显已选权限(仅按钮级码,父节点自动级联半选/全选)
    nextTick(() => {
      treeRef.value?.setCheckedKeys(codesRes.data || [], true)
    })
  } catch (error) {
    console.error('加载权限数据失败:', error)
    ElMessage.error('加载权限数据失败，请重试')
  } finally {
    permLoading.value = false
  }
}

// 提交权限分配(全量同步角色节点级权限,目录/菜单级码由后端忽略)
const handlePermSubmit = async () => {
  if (!currentRoleForPerm.value) return
  try {
    permSubmitting.value = true
    // 勾选节点(完全选中) + 半选父节点(勾选部分子项的目录/菜单)
    const checked: string[] = treeRef.value?.getCheckedKeys(false) || []
    const halfChecked: string[] = treeRef.value?.getHalfCheckedKeys() || []
    const codes = [...checked, ...halfChecked]

    const res = await syncRolePermissions(currentRoleForPerm.value.role_key, codes)
    ElMessage.success(res.message || '权限分配成功')
    permDialogVisible.value = false
  } catch (error) {
    console.error('权限分配失败:', error)
    ElMessage.error('权限分配失败，请重试')
  } finally {
    permSubmitting.value = false
  }
}

// 初始化加载数据
onMounted(() => {
  fetchData()
})
</script>
