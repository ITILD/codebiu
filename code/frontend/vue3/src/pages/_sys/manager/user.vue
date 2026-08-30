<template>
  <div p-4 md:p-6 w-full>
    <!-- 搜索栏 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <el-input class="w-full sm:w-80" v-model="searchQuery" placeholder="输入用户名搜索" clearable @clear="handleSearch" @keyup.enter="handleSearch">
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
      <el-button type="primary" @click="handleCreate">
        新增用户
      </el-button>
    </div>

    <!-- 数据表格 -->
    <el-table :data="tableData" v-loading="loading" stripe w-full>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="nickname" label="昵称" min-width="100" />
      <el-table-column label="部门" min-width="120">
        <template #default="{ row }">
          {{ getDeptName(row.dept_id) }}
        </template>
      </el-table-column>
      <el-table-column prop="email" label="邮箱" min-width="150" />
      <el-table-column prop="phone" label="电话" min-width="120" />
      <el-table-column label="状态" min-width="80">
        <template #default="{ row }">
          <el-switch v-model="row.is_active" disabled :active-text="row.is_active ? '启用' : '禁用'" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at).toLocaleString() : '' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)" plain>编辑</el-button>
          <el-button size="small" type="success" @click="handleAssignRole(row)" plain>分配角色</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)" plain>删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 编辑/创建对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[500px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item prop="username" label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select v-model="form.dept_id" :data="deptTreeData" :props="{ value: 'id', label: 'name', children: 'children' }"
            check-strictly placeholder="请选择部门" clearable w-full />
        </el-form-item>
        <el-form-item prop="email" label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱地址" />
        </el-form-item>
        <el-form-item prop="phone" label="电话">
          <el-input v-model="form.phone" placeholder="请输入电话号码" />
        </el-form-item>
        <el-form-item prop="nickname" label="昵称">
          <el-input v-model="form.nickname" placeholder="请输入昵称" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 分配角色对话框 -->
    <el-dialog v-model="roleDialogVisible" title="分配角色" width="90%" class="max-w-[500px]">
      <div mb-3>
        <span>用户名: <strong>{{ currentUserForRole?.username }}</strong></span>
      </div>
      <el-checkbox-group v-model="selectedRoleKeys">
        <div v-for="role in allRoles" :key="role.id" mb-2>
          <el-checkbox :value="role.role_key" :label="`${role.name} (${role.role_key})`" />
        </div>
      </el-checkbox-group>
      <template #footer>
        <span>
          <el-button @click="roleDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmitRoles" :loading="roleSubmitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
import { createUser, deleteUser, updateUser, getUser, listUsers } from '@/api/authorization/user'
import { getDeptTree } from '@/api/authorization/dept'
import { listAllRoles } from '@/api/authorization/role'
import { getRolesForUser, batchAddUserRoles } from '@/api/authorization/casbin'
import type { PaginationParams, PaginationResponse } from '@/types/common'
import type { User, UserCreate, UserUpdate } from '@/types/authorization/user'
import type { DeptTree } from '@/types/authorization/dept'
import type { Role } from '@/types/authorization/role'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'

// 搜索条件
const searchQuery = ref('')

// 分页参数
const pagination = ref<PaginationParams>({
  page: 1,
  size: 10
})

// 表格数据
const tableData = ref<User[]>([])
const total = ref(0)
const loading = ref(false)

// 部门树数据
const deptTreeData = ref<DeptTree[]>([])

// 对话框相关
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const submitting = ref(false)
const currentUserId = ref<string | null>(null)

// 表单数据
const formBase = {
  username: '',
  dept_id: null as string | null,
  email: '',
  phone: '',
  nickname: '',
  is_active: true,
}
const form = reactive({ ...formBase })

// 验证规则
const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '长度在 3 到 50 个字符', trigger: 'blur' }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号码', trigger: 'blur' }
  ],
}

// 对话框标题
const dialogTitle = computed(() => {
  return currentUserId.value ? '编辑用户' : '新增用户'
})

// 角色分配相关
const roleDialogVisible = ref(false)
const roleSubmitting = ref(false)
const currentUserForRole = ref<User | null>(null)
const allRoles = ref<Role[]>([])
const selectedRoleKeys = ref<string[]>([])

// 获取部门名称
const getDeptName = (deptId?: string) => {
  if (!deptId) return ''
  const findDept = (nodes: DeptTree[]): string => {
    for (const node of nodes) {
      if (node.id === deptId) return node.name
      if (node.children?.length) {
        const found = findDept(node.children)
        if (found) return found
      }
    }
    return ''
  }
  return findDept(deptTreeData.value)
}

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    const params = {
      ...pagination.value,
      username: searchQuery.value || undefined
    }
    const response: PaginationResponse<User> = await listUsers(params)
    tableData.value = response.items
    total.value = response.total
    if (response.items.length === 0 && pagination.value.page > 1) {
      pagination.value.page -= 1
      await fetchData()
    }
  } catch (error) {
    console.error('获取用户列表失败:', error)
    ElMessage.error('获取数据失败，请重试')
  } finally {
    loading.value = false
  }
}

// 加载部门树
const fetchDeptTree = async () => {
  try {
    deptTreeData.value = await getDeptTree()
  } catch (error) {
    console.error('获取部门树失败:', error)
  }
}

// 加载所有角色
const fetchAllRoles = async () => {
  try {
    allRoles.value = await listAllRoles()
  } catch (error) {
    console.error('获取角色列表失败:', error)
  }
}

// 搜索处理
const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

// 重置表单
const resetForm = () => {
  if (formRef.value) formRef.value.resetFields()
  currentUserId.value = null
  Object.assign(form, formBase)
}

// 打开创建对话框
const handleCreate = () => {
  resetForm()
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = async (row: User) => {
  try {
    resetForm()
    currentUserId.value = row.id
    const user = await getUser(row.id)
    form.username = user.username
    form.dept_id = user.dept_id || null
    form.email = user.email || ''
    form.phone = user.phone || ''
    form.nickname = user.nickname || ''
    form.is_active = user.is_active ?? true
    dialogVisible.value = true
  } catch (error) {
    console.error('获取用户详情失败:', error)
    ElMessage.error('获取用户详情失败，请重试')
  }
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return
  try {
    const valid = await formRef.value.validate()
    if (!valid) return
    submitting.value = true
    if (currentUserId.value) {
      const updateData: UserUpdate = {
        username: form.username,
        dept_id: form.dept_id || undefined,
        email: form.email,
        phone: form.phone,
        nickname: form.nickname,
        is_active: form.is_active
      }
      await updateUser(currentUserId.value, updateData)
      ElMessage.success('用户更新成功')
    } else {
      const createData: UserCreate = {
        username: form.username,
        password: '123456',
        dept_id: form.dept_id || undefined,
        email: form.email,
        phone: form.phone,
        nickname: form.nickname,
        is_active: form.is_active
      }
      await createUser(createData)
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('操作失败:', error)
    ElMessage.error(currentUserId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除操作
const handleDelete = async (row: User) => {
  try {
    await ElMessageBox.confirm('确定要删除此用户吗？此操作不可恢复。', '警告', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    if (tableData.value.length === 1 && pagination.value.page > 1) {
      pagination.value.page -= 1
    }
    fetchData()
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error('删除失败，请重试')
    }
  }
}

// 分配角色
const handleAssignRole = async (row: User) => {
  currentUserForRole.value = row
  selectedRoleKeys.value = []
  roleDialogVisible.value = true
  // 确保角色列表已加载
  if (allRoles.value.length === 0) {
    await fetchAllRoles()
  }
  // 加载用户当前角色
  try {
    const res = await getRolesForUser(row.id)
    selectedRoleKeys.value = res.data || []
  } catch (error) {
    console.error('获取用户角色失败:', error)
  }
}

// 提交角色分配
const handleSubmitRoles = async () => {
  if (!currentUserForRole.value) return
  try {
    roleSubmitting.value = true
    await batchAddUserRoles({
      user_id: currentUserForRole.value.id,
      role_keys: selectedRoleKeys.value,
      dom: '*'
    })
    ElMessage.success('角色分配成功')
    roleDialogVisible.value = false
  } catch (error) {
    console.error('角色分配失败:', error)
    ElMessage.error('角色分配失败，请重试')
  } finally {
    roleSubmitting.value = false
  }
}

// 初始化加载数据
onMounted(() => {
  fetchData()
  fetchDeptTree()
  fetchAllRoles()
})
</script>
