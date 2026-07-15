<template>
  <div p-2 w-full>
    <!-- 搜索栏 -->
    <div mb-5 flex flex-wrap items-center gap-2>
      <el-input class="w-full sm:w-80" v-model="searchQuery" placeholder="输入部门名称搜索" clearable @clear="handleSearch" @keyup.enter="handleSearch">
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
      <el-button type="primary" @click="handleCreate">
        新增部门
      </el-button>
    </div>

    <!-- 数据表格 -->
    <el-table :data="tableData" v-loading="loading" border stripe w-full row-key="id" :tree-props="{ children: 'children' }" default-expand-all>
      <el-table-column prop="name" label="部门名称" min-width="180" />
      <el-table-column prop="order_num" label="排序" min-width="80" align="center" />
      <el-table-column prop="leader" label="负责人" min-width="100" />
      <el-table-column prop="phone" label="联系电话" min-width="120" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column prop="is_active" label="状态" min-width="100" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" disabled :active-text="row.is_active ? '启用' : '禁用'" />
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" min-width="180">
        <template #default="{ row }">
          <span v-if="row.created_at">{{ formatDate(row.created_at) }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="150" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" plain @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[600px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="上级部门" prop="parent_id">
          <el-tree-select v-model="form.parent_id" :data="parentOptions" :props="treeSelectProps" check-strictly
            placeholder="请选择上级部门" w-full />
        </el-form-item>
        <el-form-item label="部门名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入部门名称" />
        </el-form-item>
        <el-form-item label="显示排序" prop="order_num">
          <el-input-number v-model="form.order_num" :min="0" />
        </el-form-item>
        <el-form-item label="负责人" prop="leader">
          <el-input v-model="form.leader" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input v-model="form.phone" placeholder="请输入联系电话" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
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
import { Search } from '@element-plus/icons-vue'
import { createDept, deleteDept, getDept, getDeptTree, updateDept } from '@/api/authorization/dept'
import type { DeptCreate, DeptTree, DeptUpdate } from '@/types/authorization/dept'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

// 树节点类型（DeptTree 树形接口未包含 created_at，此处扩展以便表格展示后端可能返回的创建时间）
interface DeptTreeNode extends DeptTree {
  created_at?: string
}

// 搜索条件
const searchQuery = ref('')

// 表格数据
const rawTreeData = ref<DeptTreeNode[]>([])
const loading = ref(false)

// 递归过滤树节点（按名称匹配，保留匹配项所在的祖先链）
const filterTree = (nodes: DeptTreeNode[], keyword: string): DeptTreeNode[] => {
  const result: DeptTreeNode[] = []
  for (const node of nodes) {
    const children = filterTree(node.children || [], keyword)
    if (node.name.includes(keyword) || children.length > 0) {
      result.push({ ...node, children })
    }
  }
  return result
}

// 搜索时实时过滤展示
const tableData = computed(() => {
  if (!searchQuery.value) return rawTreeData.value
  return filterTree(rawTreeData.value, searchQuery.value)
})

// 上级部门下拉树数据（以 "0" 作为根选项）
const treeSelectProps = {
  value: 'id',
  label: 'name',
  children: 'children'
}
const parentOptions = computed(() => [
  {
    id: '0',
    name: '主类目',
    children: rawTreeData.value
  }
])

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentDeptId = ref<string | null>(null)

// 表单数据
const formBase = {
  parent_id: '0',
  name: '',
  order_num: 0,
  leader: '',
  phone: '',
  email: '',
  is_active: true
}
const form_copy = JSON.parse(JSON.stringify(formBase))
const form = reactive(form_copy)

// 表单校验规则
const rules = {
  name: [
    { required: true, message: '请输入部门名称', trigger: 'blur' },
    { max: 50, message: '长度不超过 50 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号码', trigger: 'blur' }
  ]
}

// 对话框标题
const dialogTitle = computed(() => {
  return currentDeptId.value ? '编辑部门' : '新增部门'
})

// 日期格式化
const formatDate = (value: string | number | Date) => new Date(value).toLocaleString()

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    rawTreeData.value = await getDeptTree()
  } catch (error) {
    console.error('获取部门树失败:', error)
    ElMessage.error('获取数据失败，请重试')
  } finally {
    loading.value = false
  }
}

// 搜索处理（搜索为前端实时过滤，此处可触发表格刷新占位）
const handleSearch = () => {
  // tableData 为 computed，输入时已自动过滤，无需额外请求
}

// 重置表单
const resetForm = () => {
  if (formRef.value) formRef.value.resetFields()
  currentDeptId.value = null
  Object.assign(form, JSON.parse(JSON.stringify(formBase)))
}

// 打开创建对话框
const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = async (row: DeptTreeNode) => {
  try {
    resetForm()
    currentDeptId.value = row.id

    // 获取部门详情
    const dept = await getDept(row.id)
    form.parent_id = dept.parent_id || '0'
    form.name = dept.name
    form.order_num = dept.order_num
    form.leader = dept.leader || ''
    form.phone = dept.phone || ''
    form.email = dept.email || ''
    form.is_active = dept.is_active

    dialogVisible.value = true
  } catch (error) {
    console.error('获取部门详情失败:', error)
    ElMessage.error('获取部门详情失败，请重试')
  }
}

// 提交表单（创建或更新）
const handleSubmit = async () => {
  if (!formRef.value) return

  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    submitting.value = true

    if (currentDeptId.value) {
      // 更新部门
      const updateData: DeptUpdate = {
        parent_id: form.parent_id,
        name: form.name,
        order_num: form.order_num,
        leader: form.leader,
        phone: form.phone,
        email: form.email,
        is_active: form.is_active
      }
      await updateDept(currentDeptId.value, updateData)
      ElMessage.success('部门更新成功')
    } else {
      // 创建部门
      const createData: DeptCreate = {
        parent_id: form.parent_id,
        name: form.name,
        order_num: form.order_num,
        leader: form.leader,
        phone: form.phone,
        email: form.email,
        is_active: form.is_active
      }
      await createDept(createData)
      ElMessage.success('部门创建成功')
    }

    dialogVisible.value = false
    fetchData() // 刷新数据
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentDeptId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: DeptTreeNode) => {
  try {
    await ElMessageBox.confirm('确定要删除此部门吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })

    await deleteDept(row.id)
    ElMessage.success('删除成功')
    fetchData() // 刷新数据
  } catch (error) {
    // 用户取消删除时不报错
    if (error === 'cancel' || error === 'close') return
    console.error('删除失败:', error)
    ElMessage.error('删除失败，请重试')
  }
}

// 初始化加载数据
onMounted(() => {
  fetchData()
})
</script>
