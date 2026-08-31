<template>
  <div p-2 w-full>
    <!-- 页头: 返回 + 项目名 + 添加成员 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <el-button :icon="Back" @click="router.push('/_sys/rag/project')" />
      <span font-bold text-lg>{{ projectName }}</span>
      <el-tag v-if="projectId" size="small">成员管理</el-tag>
      <div flex-1 />
      <el-button type="primary" :icon="Plus" @click="handleAdd" :disabled="!projectId">
        添加成员
      </el-button>
    </div>

    <!-- 统一搜索栏: 多字段筛选(用户关键字/角色) -->
    <TableSearchBar
      v-model="queryParams"
      :fields="searchFields"
      :collapse-count="2"
      @search="handleSearch"
      @reset="handleSearch"
    />

    <!-- 成员表格 -->
    <el-table v-loading="loading" :data="members" border stripe>
      <el-table-column label="成员" min-width="200">
        <template #default="{ row }">
          <div flex items-center gap-2>
            <el-avatar :size="32" :icon="UserFilled" />
            <div>
              <div>{{ userLabel(row.user_id) }}</div>
              <div text-xs text-gray-4>{{ row.user_id }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="角色" width="180" align="center">
        <template #default="{ row }">
          <el-select :model-value="row.role" size="small" w-32 @change="(val: string) => handleRoleChange(row, val)">
            <el-option v-for="opt in ragRoleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="加入时间" width="130" align="center">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" align="center" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="danger" plain @click="handleRemove(row)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态提示 -->
    <div v-if="!loading && members.length === 0" py-16 flex flex-col items-center text-gray-4>
      <el-icon text-5xl mb-3><UserFilled /></el-icon>
      <p m-0 v-if="projectId">暂无成员，点击右上角"添加成员"开始</p>
      <p m-0 v-else>缺少项目参数，请从知识库页面进入</p>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 添加成员对话框 -->
    <el-dialog v-model="dialogVisible" title="添加成员" width="90%" class="max-w-[480px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="用户" prop="user_id">
          <el-select v-model="form.user_id" filterable placeholder="搜索并选择用户" w-full :loading="userLoading">
            <el-option v-for="u in userOptions" :key="u.id" :label="`${u.nickname || u.username} (${u.username})`"
              :value="u.id">
              <div flex items-center justify-between>
                <span>{{ u.nickname || u.username }}</span>
                <span text-xs text-gray-4>{{ u.username }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" placeholder="请选择角色" w-full>
            <el-option v-for="opt in ragRoleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Back, Plus, UserFilled } from '@element-plus/icons-vue'
import {
  addProjectMember,
  listProjectMembers,
  removeProjectMember,
  updateProjectMember,
} from '@/api/rag/member'
import { listRagProjects } from '@/api/rag/project'
import { listUsers } from '@/api/authorization/user'
import { ragRoleOptions, type ProjectMember } from '@/types/rag'
import TableSearchBar, { type SearchField } from '@/components/app/sys/TableSearchBar.vue'
import type { User } from '@/types/authorization/user'
import type { PaginationParams } from '@/types/common'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// 路径参数中的项目ID
const projectId = computed(() => (route.query.project_id as string) || '')
const projectName = ref('知识库成员')

// 分页参数
const pagination = ref<PaginationParams>({ page: 1, size: 20 })
const total = ref(0)
const loading = ref(false)

// 搜索字段配置(用户关键字/角色多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'user_keyword', label: '成员', placeholder: '用户名/昵称' },
  {
    prop: 'role', label: '角色', type: 'select',
    options: ragRoleOptions.map(o => ({ label: o.label, value: o.value as string })),
  },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  user_keyword: '',
  role: undefined,
})

// 成员列表
const members = ref<ProjectMember[]>([])

// 用户缓存(用于成员列表显示用户名)
const userMap = ref<Map<string, User>>(new Map())
const userOptions = ref<User[]>([])
const userLoading = false

// 添加成员对话框
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ user_id: '', role: 'project_reader' })

const rules = {
  user_id: [{ required: true, message: '请选择用户', trigger: 'change' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

// 用户显示名(优先昵称)
const userLabel = (userId: string) => {
  const u = userMap.value.get(userId)
  return u ? (u.nickname || u.username) : userId
}

// 日期格式化
const formatDate = (value: string) => new Date(value).toLocaleDateString()

// 加载项目名称
const loadProjectName = async () => {
  if (!projectId.value) return
  try {
    const res = await listRagProjects({ page: 1, size: 200 })
    const found = res.items.find((p) => p.id === projectId.value)
    if (found) projectName.value = found.name
  } catch {
    // 名称加载失败不影响列表展示
  }
}

// 加载用户列表(用于显示与选择)
const loadUsers = async () => {
  try {
    const res = await listUsers({ page: 1, size: 500 })
    userOptions.value = res.items
    userMap.value = new Map(res.items.map((u) => [u.id, u]))
  } catch (error) {
    console.error('获取用户列表失败:', error)
  }
}

// 获取成员列表(携带多字段过滤参数)
const fetchData = async () => {
  if (!projectId.value) return
  try {
    loading.value = true
    const { user_keyword, role } = queryParams.value
    const res = await listProjectMembers(projectId.value, {
      ...pagination.value,
      user_keyword: (user_keyword as string) || undefined,
      role: (role as string) || undefined,
    })
    members.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('获取成员列表失败:', error)
    ElMessage.error('获取成员列表失败')
  } finally {
    loading.value = false
  }
}

/** 搜索/重置: 回到第一页后重新查询 */
const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

// 打开添加成员对话框
const handleAdd = () => {
  Object.assign(form, { user_id: '', role: 'project_reader' })
  dialogVisible.value = true
}

// 提交添加成员
const handleSubmit = async () => {
  if (!formRef.value || !projectId.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    submitting.value = true
    await addProjectMember({
      user_id: form.user_id,
      project_id: projectId.value,
      role: form.role,
    })
    ElMessage.success('成员添加成功')
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('添加失败:', error)
    ElMessage.error('添加失败')
  } finally {
    submitting.value = false
  }
}

// 切换成员角色
const handleRoleChange = async (row: ProjectMember, role: string) => {
  try {
    await updateProjectMember(row.id, { role })
    row.role = role
    ElMessage.success('角色已更新')
  } catch (error) {
    console.error('角色更新失败:', error)
    ElMessage.error('角色更新失败')
  }
}

// 移除成员
const handleRemove = async (row: ProjectMember) => {
  try {
    await ElMessageBox.confirm(
      `确定移除成员"${userLabel(row.user_id)}"吗？其将失去该知识库的访问权限。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await removeProjectMember(row.id)
    ElMessage.success('成员已移除')
    fetchData()
  } catch (error) {
    console.log('取消移除或移除失败:', error)
  }
}

onMounted(() => {
  loadProjectName()
  loadUsers()
  fetchData()
})

// 项目参数变化时刷新
watch(projectId, () => {
  pagination.value.page = 1
  loadProjectName()
  fetchData()
})
</script>
