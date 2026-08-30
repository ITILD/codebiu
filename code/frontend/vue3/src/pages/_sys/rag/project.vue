<template>
  <div p-4 md:p-6 w-full>
    <!-- 工具栏 -->
    <div mb-4 flex flex-wrap items-center gap-2>
      <div w-full sm:w-48 shrink-0>
        <el-select v-model="kbCategory" w-full placeholder="全部分类" clearable
          @change="handleSearch">
          <el-option v-for="opt in kbCategoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>
      <el-input class="w-full sm:w-60" v-model="searchQuery" placeholder="输入知识库名称搜索" clearable
        @clear="handleSearch" @keyup.enter="handleSearch">
        <template #append>
          <el-button :icon="Search" @click="handleSearch" />
        </template>
      </el-input>
      <el-button type="primary" @click="handleCreate">
        新建知识库
      </el-button>
    </div>

    <!-- 知识库卡片列表 -->
    <div v-loading="loading" grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4>
      <div v-for="item in filteredProjects" :key="item.id"
        p-4 rounded-xl border border-note bg-note-card hover:shadow-note hover:-translate-y-0.5 transition-all duration-300 flex flex-col gap-2>
        <!-- 标题行 -->
        <div flex items-center justify-between gap-2>
          <div flex items-center gap-2 min-w-0>
            <el-icon text-xl text-blue-5><Collection /></el-icon>
            <span font-bold truncate :title="item.name">{{ item.name }}</span>
          </div>
          <el-tag size="small" :type="categoryTagType(item.kb_category)">
            {{ categoryLabel(item.kb_category) }}
          </el-tag>
        </div>
        <!-- 描述 -->
        <p text-sm text-gray-5 h-10 m-0 line-clamp-2 :title="item.description ?? undefined">
          {{ item.description || '暂无描述' }}
        </p>
        <!-- 元信息 -->
        <div flex items-center gap-3 text-xs text-gray-4>
          <span flex items-center gap-1>
            <el-icon><Lock v-if="item.is_private" /><Unlock v-else /></el-icon>
            {{ item.is_private ? '私有' : '公开' }}
          </span>
          <span flex items-center gap-1>
            <el-icon><Clock /></el-icon>
            {{ formatDate(item.created_at) }}
          </span>
        </div>
        <!-- 操作按钮 -->
        <div flex gap-1 mt-1>
          <el-button size="small" type="primary" plain flex-1
            @click="router.push(`/_sys/rag/document?project_id=${item.id}`)">
            文档
          </el-button>
          <el-button size="small" type="success" plain flex-1
            @click="router.push(`/_sys/rag/member?project_id=${item.id}`)">
            成员
          </el-button>
          <el-button size="small" type="warning" plain @click="handleEdit(item)">
            编辑
          </el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(item)">
            删除
          </el-button>
        </div>
      </div>
      <!-- 空状态 -->
      <div v-if="!loading && filteredProjects.length === 0" col-span-full py-16 flex flex-col items-center
        text-gray-4>
        <el-icon text-5xl mb-3><FolderOpened /></el-icon>
        <p m-0>暂无知识库，点击右上角"新建知识库"开始</p>
      </div>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-4 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="90%" class="max-w-[520px]">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入知识库名称" maxlength="100" />
        </el-form-item>
        <el-form-item label="分类" prop="kb_category">
          <el-select v-model="form.kb_category" placeholder="请选择分类" w-full>
            <el-option v-for="opt in kbCategoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
        </el-form-item>
        <el-form-item label="是否私有">
          <el-switch v-model="form.is_private" />
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
import { Search, Collection, Lock, Unlock, Clock, FolderOpened } from '@element-plus/icons-vue'
import {
  createRagProject,
  deleteRagProject,
  listRagProjects,
  updateRagProject,
} from '@/api/rag/project'
import {
  KbCategory,
  kbCategoryOptions,
  type Project,
  type ProjectCreate,
} from '@/types/rag'
import type { PaginationParams } from '@/types/common'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()

// 分页参数
const pagination = ref<PaginationParams>({ page: 1, size: 12 })
const total = ref(0)
const loading = ref(false)

// 列表数据与过滤
const projects = ref<Project[]>([])
const searchQuery = ref('')
const kbCategory = ref<string | undefined>(undefined)

// 对话框
const dialogVisible = ref(false)
const submitting = ref(false)
const currentId = ref<string | null>(null)
const formRef = ref<FormInstance>()

const formBase = {
  name: '',
  description: '',
  is_private: true,
  kb_category: KbCategory.PROJECT as string,
}
const form = reactive({ ...formBase })

const rules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
  kb_category: [{ required: true, message: '请选择分类', trigger: 'change' }],
}

const dialogTitle = computed(() => (currentId.value ? '编辑知识库' : '新建知识库'))

// 客户端按名称过滤
const filteredProjects = computed(() =>
  projects.value.filter((p) => p.name.includes(searchQuery.value))
)

// 分类标签配置
const categoryLabel = (value: string) =>
  kbCategoryOptions.find((o) => o.value === value)?.label || value
const categoryTagType = (value: string) => {
  switch (value) {
    case KbCategory.PERSONAL:
      return 'success'
    case KbCategory.COMPANY:
      return 'warning'
    default:
      return 'primary'
  }
}

// 日期格式化
const formatDate = (value: string) => new Date(value).toLocaleDateString()

// 获取数据
const fetchData = async () => {
  try {
    loading.value = true
    const res = await listRagProjects(
      pagination.value,
      kbCategory.value || undefined
    )
    projects.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('获取知识库列表失败:', error)
    ElMessage.error('获取知识库列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.value.page = 1
  fetchData()
}

// 打开创建对话框
const handleCreate = () => {
  currentId.value = null
  Object.assign(form, formBase)
  dialogVisible.value = true
}

// 打开编辑对话框
const handleEdit = (row: Project) => {
  currentId.value = row.id
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    is_private: row.is_private,
    kb_category: row.kb_category,
  })
  dialogVisible.value = true
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    submitting.value = true
    if (currentId.value) {
      await updateRagProject(currentId.value, { ...form })
      ElMessage.success('知识库更新成功')
    } else {
      const data: ProjectCreate = { ...form }
      await createRagProject(data)
      ElMessage.success('知识库创建成功')
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

// 删除
const handleDelete = async (row: Project) => {
  try {
    await ElMessageBox.confirm(
      `确定删除知识库"${row.name}"吗？文档、成员及向量数据将一并清理。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteRagProject(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

onMounted(() => {
  fetchData()
})
</script>
