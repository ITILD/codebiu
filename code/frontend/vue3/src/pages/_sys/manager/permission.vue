<template>
  <div p-2 w-full>
    <!-- 搜索栏 -->
    <div mb-5 flex flex-wrap items-center gap-2>
      <el-input class="w-full sm:w-80" v-model="searchQuery" placeholder="输入菜单名称搜索" clearable />
      <el-button type="primary" @click="handleCreate">
        新增权限
      </el-button>
    </div>

    <!-- 树形数据表格 -->
    <el-table :data="filteredTree" v-loading="loading" border stripe w-full row-key="id"
      :tree-props="{ children: 'children' }" default-expand-all>
      <el-table-column prop="name" label="菜单名称" min-width="180" />
      <el-table-column prop="menu_type" label="菜单类型" min-width="100">
        <template #default="{ row }">
          <el-tag :type="menuTypeTagType(row.menu_type)">{{ menuTypeLabel(row.menu_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="perms" label="权限标识" min-width="160" />
      <el-table-column prop="code" label="权限代码" min-width="140" />
      <el-table-column prop="path" label="路由路径" min-width="140" />
      <el-table-column prop="component" label="组件路径" min-width="160" />
      <el-table-column prop="order_num" label="排序" min-width="80" />
      <el-table-column prop="visible" label="可见" min-width="80">
        <template #default="{ row }">
          <el-switch v-model="row.visible" disabled />
        </template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" min-width="80">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" disabled />
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="success" plain @click="handleAddChild(row)">新增子项</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[600px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="上级菜单" prop="parent_id">
          <el-tree-select v-model="form.parent_id" :data="parentTreeData"
            :props="{ label: 'name', children: 'children' }" node-key="id" check-strictly default-expand-all
            placeholder="请选择上级菜单" w-full />
        </el-form-item>
        <el-form-item label="菜单类型" prop="menu_type">
          <el-radio-group v-model="form.menu_type">
            <el-radio v-for="item in menuTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="菜单名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入菜单名称" />
        </el-form-item>
        <el-form-item label="权限代码" prop="code">
          <el-input v-model="form.code" placeholder="请输入权限代码" />
        </el-form-item>
        <el-form-item label="权限标识" prop="perms">
          <el-input v-model="form.perms" placeholder="如：system:user:list" />
        </el-form-item>
        <el-form-item v-if="form.menu_type === 'M' || form.menu_type === 'C'" label="路由路径" prop="path">
          <el-input v-model="form.path" placeholder="请输入路由路径" />
        </el-form-item>
        <el-form-item v-if="form.menu_type === 'C'" label="组件路径" prop="component">
          <el-input v-model="form.component" placeholder="请输入组件路径" />
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="请输入图标" />
        </el-form-item>
        <el-form-item label="显示排序" prop="order_num">
          <el-input-number v-model="form.order_num" :min="0" />
        </el-form-item>
        <el-form-item label="是否可见" prop="visible">
          <el-switch v-model="form.visible" />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
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
import {
  createPermission,
  deletePermission,
  getPermission,
  getPermissionTree,
  updatePermission,
} from '@/api/authorization/permission'
import { menuTypeOptions } from '@/types/authorization/permission'
import type {
  PermissionCreate,
  PermissionTree,
  PermissionUpdate,
} from '@/types/authorization/permission'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// 搜索条件
const searchQuery = ref('')

// 表格数据（树形）
const permissionTree = ref<PermissionTree[]>([])
const loading = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentId = ref<string | null>(null)

// 表单基础数据
const formBase = {
  parent_id: '0',
  menu_type: 'M',
  name: '',
  code: '',
  perms: '',
  path: '',
  component: '',
  icon: '',
  order_num: 0,
  visible: true,
  is_active: true,
  description: '',
}

const form = reactive({ ...formBase })

// 表单验证规则
const rules = {
  name: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入权限代码', trigger: 'blur' }],
}

// 对话框标题
const dialogTitle = computed(() => {
  return currentId.value ? '编辑权限' : '新增权限'
})

// 上级菜单树数据（含根目录）
const parentTreeData = computed(() => [
  {
    id: '0',
    name: '根目录',
    children: permissionTree.value,
  },
])

// 菜单类型标签样式
const menuTypeTagType = (type: string) => {
  switch (type) {
    case 'M':
      return 'warning'
    case 'C':
      return 'primary'
    case 'F':
      return 'info'
    default:
      return 'info'
  }
}

// 菜单类型标签文字
const menuTypeLabel = (type: string) => {
  return menuTypeOptions.find((o) => o.value === type)?.label || type
}

// 客户端按名称过滤树（保留匹配节点的祖先链）
const filterTree = (nodes: PermissionTree[], query: string): PermissionTree[] => {
  if (!query) return nodes
  const result: PermissionTree[] = []
  for (const node of nodes) {
    const children = filterTree(node.children || [], query)
    if (node.name.includes(query) || children.length > 0) {
      result.push({ ...node, children })
    }
  }
  return result
}

const filteredTree = computed(() => filterTree(permissionTree.value, searchQuery.value))

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    permissionTree.value = await getPermissionTree()
  } catch (error) {
    console.error('获取权限树失败:', error)
    ElMessage.error('获取数据失败，请重试')
  } finally {
    loading.value = false
  }
}

// 重置表单
const resetForm = () => {
  if (formRef.value) formRef.value.resetFields()
  currentId.value = null
  Object.assign(form, formBase)
}

// 打开创建对话框
const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

// 新增子项：预填 parent_id
const handleAddChild = (row: PermissionTree) => {
  resetForm()
  form.parent_id = row.id
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = async (row: PermissionTree) => {
  try {
    resetForm()
    currentId.value = row.id

    const detail = await getPermission(row.id)
    form.parent_id = detail.parent_id || '0'
    form.menu_type = detail.menu_type
    form.name = detail.name
    form.code = detail.code
    form.perms = detail.perms || ''
    form.path = detail.path || ''
    form.component = detail.component || ''
    form.icon = detail.icon || ''
    form.order_num = detail.order_num
    form.visible = detail.visible
    form.is_active = detail.is_active
    form.description = detail.description || ''

    dialogVisible.value = true
  } catch (error) {
    console.error('获取权限详情失败:', error)
    ElMessage.error('获取权限详情失败，请重试')
  }
}

// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentId.value) {
      const updateData: PermissionUpdate = {
        parent_id: form.parent_id,
        name: form.name,
        code: form.code,
        description: form.description,
        menu_type: form.menu_type,
        path: form.path,
        component: form.component,
        perms: form.perms,
        icon: form.icon,
        order_num: form.order_num,
        visible: form.visible,
        is_active: form.is_active,
      }
      await updatePermission(currentId.value, updateData)
      ElMessage.success('权限更新成功')
    } else {
      const createData: PermissionCreate = {
        parent_id: form.parent_id,
        name: form.name,
        code: form.code,
        description: form.description,
        menu_type: form.menu_type,
        path: form.path,
        component: form.component,
        perms: form.perms,
        icon: form.icon,
        order_num: form.order_num,
        visible: form.visible,
        is_active: form.is_active,
      }
      await createPermission(createData)
      ElMessage.success('权限创建成功')
    }

    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: PermissionTree) => {
  try {
    await ElMessageBox.confirm('确定要删除此权限吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })

    await deletePermission(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
    ElMessage.error('删除失败，请重试')
  }
}

// 初始化加载数据
onMounted(() => {
  fetchData()
})
</script>
