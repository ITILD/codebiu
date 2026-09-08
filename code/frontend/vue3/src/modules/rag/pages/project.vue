<template>
  <div p-4 md:p-6 w-full>
    <!-- 模块内页导航(应用页无侧边栏, 孙页面切换在此) -->
    <RagPageNav class="mb-4" />

    <!-- 视图切换: 项目列表 / 文档列表(跨项目) -->
    <div mb-3 flex flex-wrap items-center gap-2>
      <el-radio-group v-model="viewMode">
        <el-radio-button value="projects">知识库项目</el-radio-button>
        <el-radio-button value="documents">知识库文档</el-radio-button>
      </el-radio-group>
      <el-button v-if="viewMode === 'documents'" :icon="Refresh" circle title="刷新" :loading="docLoading"
        @click="loadDocList" />
    </div>

    <!-- ===== 视图一: 知识库项目 ===== -->
    <template v-if="viewMode === 'projects'">
      <!-- 统一搜索栏: 多字段筛选(名称/分类/私有状态) -->
      <TableSearchBar
        v-model="queryParams"
        :fields="searchFields"
        @search="handleSearch"
        @reset="handleSearch"
      >
        <template #actions>
          <el-button type="primary" @click="handleCreate">
            新建知识库
          </el-button>
        </template>
      </TableSearchBar>

      <!-- 项目卡片网格(便签风: 柔和阴影/圆角/绿色点缀, 点击卡片进入设置) -->
      <div v-loading="loading" grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3>
        <div
          v-for="row in projects" :key="row.id"
          flex flex-col gap-3 p-4 rounded-2xl border border-note bg-note-card shadow-note cursor-pointer
          hover:border-note-green hover:-translate-y-0.5 transition-all
          @click="handleOpenEdit(row)"
        >
          <!-- 头部: 图标 + 名称 + 创建时间 -->
          <div flex items-center gap-2.5>
            <div w-10 h-10 rounded-xl bg-note-tint flex-center shrink-0>
              <el-icon :size="20" text-note-green><Collection /></el-icon>
            </div>
            <div min-w-0 flex-1>
              <div font-medium text-note truncate>{{ row.name }}</div>
              <div text-xs text-note-sub mt-0.5>{{ formatDate(row.created_at) }} 创建</div>
            </div>
          </div>
          <!-- 描述 -->
          <p text-sm text-note-sub leading-relaxed line-clamp-2 min-h-10 m-0>
            {{ row.description || '暂无描述' }}
          </p>
          <!-- 底部: 分类/可见性标签 + 操作 -->
          <div flex items-center justify-between pt-2.5 border-t border-note>
            <div flex items-center gap-1.5 min-w-0>
              <el-tag size="small" effect="plain" :type="categoryTagType(row.kb_category)">
                {{ categoryLabel(row.kb_category) }}
              </el-tag>
              <el-tag size="small" effect="plain" type="info">
                <el-icon :size="11" mr-0.5><Lock v-if="row.is_private" /><Unlock v-else /></el-icon>
                {{ row.is_private ? '私有' : '公开' }}
              </el-tag>
            </div>
            <div flex items-center gap-1 @click.stop>
              <el-button size="small" text bg type="primary" @click="handleOpenEdit(row)">设置</el-button>
              <el-button size="small" text bg type="danger" @click="handleDelete(row)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!loading && projects.length === 0" py-16 flex flex-col items-center text-note-sub>
        <el-icon text-5xl mb-3 class="opacity-40"><FolderOpened /></el-icon>
        <p m-0>暂无知识库，点击右上角"新建知识库"开始</p>
      </div>

      <!-- 分页(手机居中, 桌面靠右) -->
      <div mt-4 flex flex-wrap justify-center sm:justify-end>
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
          :total="total" layout="total, prev, pager, next"
          @size-change="fetchData" @current-change="fetchData" />
      </div>
    </template>

    <!-- ===== 视图二: 知识库文档(跨项目汇总, 前端过滤) ===== -->
    <template v-else>
      <TableSearchBar v-model="docQueryParams" :fields="docSearchFields" :collapse-count="2" />

      <!-- 便签风卡片容器 -->
      <div rounded-2xl border border-note bg-note-card shadow-note overflow-hidden>
      <el-table v-loading="docLoading" :data="docPageData" stripe>
        <el-table-column label="文档名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div flex items-center gap-2>
              <el-icon text-lg :class="fileIconClass(row.file_extension)"><Document /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" min-width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ (row.file_extension || '').toUpperCase() || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="所属项目" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <div flex items-center gap-1.5>
              <el-icon text-note-green><Collection /></el-icon>
              {{ row.project_name }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" min-width="110" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="row.parse_status === ParseStatus.FAILED && row.error_message"
              :content="row.error_message" placement="top">
              <el-tag size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
                {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status }}
              </el-tag>
            </el-tooltip>
            <el-tag v-else size="small" :type="parseStatusOptions[row.parse_status]?.tag ?? 'info'">
              {{ parseStatusOptions[row.parse_status]?.label ?? row.parse_status ?? '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" min-width="100" align="center">
          <template #default="{ row }">
            {{ formatSize(row.file_size_bytes) }}
          </template>
        </el-table-column>
        <el-table-column label="描述" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.description || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="更新时间" min-width="110" align="center">
          <template #default="{ row }">
            {{ formatDate(row.updated_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="140" align="center" :fixed="isMd ? 'right' : false">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="handleDocDownload(row)">下载</el-button>
            <el-button size="small" type="danger" plain @click="handleDocDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      </div>

      <!-- 空状态 -->
      <div v-if="!docLoading && filteredDocs.length === 0" py-16 flex flex-col items-center text-note-sub>
        <el-icon text-5xl mb-3 class="opacity-40"><Document /></el-icon>
        <p m-0>暂无文档，可在知识库编辑抽屉的"文档管理"中上传</p>
      </div>

      <!-- 分页(前端分页) -->
      <div mt-4 flex flex-wrap justify-center sm:justify-end>
        <el-pagination v-model:current-page="docPagination.page" v-model:page-size="docPagination.size"
          :total="filteredDocs.length" layout="total, prev, pager, next" />
      </div>
    </template>

    <!-- 新建知识库对话框(编辑在抽屉中完成) -->
    <el-dialog v-model="dialogVisible" title="新建知识库" width="90%" class="max-w-[520px]">
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
          <el-button type="primary" @click="handleCreateSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 知识库设置抽屉: 基本信息 / 文档管理 / 成员管理(内嵌面板, 免独立子页) -->
    <el-drawer v-model="drawerVisible" :title="drawerTitle" size="62%" destroy-on-close class="kb-setting-drawer">
      <el-tabs v-model="drawerTab">
        <el-tab-pane label="基本信息" name="info">
          <!-- 便签风表单卡片 -->
          <el-form
            :model="editForm" :rules="rules" ref="editFormRef" label-width="90px"
            class="max-w-[520px] p-5 rounded-2xl border border-note bg-note-soft/60"
          >
            <el-form-item label="名称" prop="name">
              <el-input v-model="editForm.name" placeholder="请输入知识库名称" maxlength="100" />
            </el-form-item>
            <el-form-item label="分类" prop="kb_category">
              <el-select v-model="editForm.kb_category" placeholder="请选择分类" w-full>
                <el-option v-for="opt in kbCategoryOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="描述" prop="description">
              <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
            </el-form-item>
            <el-form-item label="是否私有">
              <el-switch v-model="editForm.is_private" />
            </el-form-item>
            <el-form-item>
              <el-button class="px-6" :loading="savingBasic" @click="handleSaveBasic">保存</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane v-if="hasPerm('rag:doc')" label="文档管理" name="docs" lazy>
          <DocumentManage :project-id="currentProject!.id" />
        </el-tab-pane>
        <el-tab-pane v-if="hasPerm('rag:member')" label="成员管理" name="members" lazy>
          <MemberManage :project-id="currentProject!.id" />
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { Collection, Lock, Unlock, FolderOpened, Document, Refresh } from '@element-plus/icons-vue'
import {
  createRagProject,
  deleteRagProject,
  listRagProjects,
  updateRagProject,
} from '../api/project'
import {
  listRagProjectDocuments,
  deleteRagDocument,
  getRagDocumentDownloadUrl,
} from '../api/document'
import {
  KbCategory,
  kbCategoryOptions,
  ParseStatus,
  parseStatusOptions,
  type Project,
  type ProjectCreate,
} from '../types'
import TableSearchBar, { type SearchField } from '@/common/components/TableSearchBar.vue'
import RagPageNav from '../components/RagPageNav.vue'
import DocumentManage from '../components/DocumentManage.vue'
import MemberManage from '../components/MemberManage.vue'
import { usePermission } from '@/common/composables/usePermission'
import { useResponsive } from '@/common/composables/useResponsive'
import type { PaginationParams } from '@/common/types/common'
import type { ProjectDocument } from '../types'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'

const { hasPerm } = usePermission()
const { isMd } = useResponsive()

// ==================== 项目列表视图 ====================

// 分页参数
const pagination = ref<PaginationParams>({ page: 1, size: 12 })
const total = ref(0)
const loading = ref(false)

// 视图切换(projects=项目列表 / documents=文档列表)
const viewMode = ref<'projects' | 'documents'>('projects')

// 搜索字段配置(名称/分类/私有状态多字段筛选)
const searchFields: SearchField[] = [
  { prop: 'name', label: '名称', placeholder: '知识库名称' },
  {
    prop: 'kb_category', label: '分类', type: 'select',
    options: kbCategoryOptions.map(o => ({ label: o.label, value: o.value as string })),
  },
  {
    prop: 'is_private', label: '可见性', type: 'select', options: [
      { label: '私有', value: true },
      { label: '公开', value: false },
    ],
  },
]
// 查询参数(与后端列表接口过滤参数对齐)
const queryParams = ref<Record<string, unknown>>({
  name: '',
  kb_category: undefined,
  is_private: undefined,
})

// 列表数据
const projects = ref<Project[]>([])

// 新建知识库对话框
const dialogVisible = ref(false)
const submitting = ref(false)
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

// 文件大小格式化(文档视图用)
const formatSize = (bytes: number | null) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

// 文件图标按扩展名着色
const fileIconClass = (ext: string) => {
  const e = (ext || '').toLowerCase()
  if (['pdf'].includes(e)) return 'text-red-500'
  if (['doc', 'docx'].includes(e)) return 'text-blue-500'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'text-green-500'
  if (['ppt', 'pptx'].includes(e)) return 'text-orange-500'
  return 'text-note-sub'
}

// 获取项目列表(携带多字段过滤参数)
const fetchData = async () => {
  try {
    loading.value = true
    const { name, kb_category, is_private } = queryParams.value
    const res = await listRagProjects({
      ...pagination.value,
      name: (name as string) || undefined,
      kb_category: (kb_category as string) || undefined,
      is_private: (is_private as boolean | undefined) ?? undefined,
    })
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

// 打开新建对话框
const handleCreate = () => {
  Object.assign(form, formBase)
  dialogVisible.value = true
}

// 提交新建
const handleCreateSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    submitting.value = true
    const data: ProjectCreate = { ...form }
    await createRagProject(data)
    ElMessage.success('知识库创建成功')
    dialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('创建失败:', error)
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

// 删除项目
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

// ==================== 知识库设置抽屉(基本信息/文档/成员) ====================

const drawerVisible = ref(false)
const drawerTab = ref('info')
const currentProject = ref<Project | null>(null)
const drawerTitle = computed(() =>
  currentProject.value ? `知识库设置 - ${currentProject.value.name}` : '知识库设置'
)

// 基本信息编辑表单
const editFormRef = ref<FormInstance>()
const editForm = reactive({ ...formBase })
const savingBasic = ref(false)

// 打开编辑抽屉
const handleOpenEdit = (row: Project) => {
  currentProject.value = row
  Object.assign(editForm, {
    name: row.name,
    description: row.description || '',
    is_private: row.is_private,
    kb_category: row.kb_category,
  })
  drawerTab.value = 'info'
  drawerVisible.value = true
}

// 保存基本信息
const handleSaveBasic = async () => {
  if (!editFormRef.value || !currentProject.value) return
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    savingBasic.value = true
    await updateRagProject(currentProject.value.id, { ...editForm })
    ElMessage.success('知识库更新成功')
    currentProject.value = { ...currentProject.value, ...editForm }
    fetchData()
  } catch (error) {
    console.error('更新失败:', error)
    ElMessage.error('更新失败')
  } finally {
    savingBasic.value = false
  }
}

// ==================== 文档列表视图(跨项目汇总) ====================

// 文档视图过滤字段(与项目视图不同: 关键字/所属项目/解析状态)
const docSearchFields: SearchField[] = [
  { prop: 'name', label: '文档', placeholder: '文档名称' },
  {
    prop: 'project_id', label: '所属项目', type: 'select', width: '200px',
    options: [],
  },
  {
    prop: 'parse_status', label: '解析状态', type: 'select',
    options: Object.entries(parseStatusOptions).map(([value, o]) => ({ label: o.label, value })),
  },
]
const docQueryParams = ref<Record<string, unknown>>({
  name: '',
  project_id: undefined,
  parse_status: undefined,
})

// 跨项目文档汇总(附所属项目名)
type DocRow = ProjectDocument & { project_name: string }
const allDocs = ref<DocRow[]>([])
const projectOptions = ref<Project[]>([])
const docLoading = ref(false)
const docPagination = ref<PaginationParams>({ page: 1, size: 20 })

// 加载文档列表(项目下拉数据 + 各项目文档汇总)
const loadDocList = async () => {
  try {
    docLoading.value = true
    const projs = await listRagProjects({ page: 1, size: 200 })
    projectOptions.value = projs.items
    // 动态填充"所属项目"下拉选项
    docSearchFields[1].options = projs.items.map((p) => ({ label: p.name, value: p.id }))
    const nameMap = new Map(projs.items.map((p) => [p.id, p.name]))
    const results = await Promise.all(
      projs.items.map((p) =>
        listRagProjectDocuments(p.id, { page: 1, size: 500 }).catch(() => ({ items: [], total: 0 }))
      )
    )
    allDocs.value = results.flatMap((r, i) =>
      r.items.map((d) => ({ ...d, project_name: nameMap.get(d.project_id) ?? d.project_id }))
    )
    docPagination.value.page = 1
  } catch (error) {
    console.error('获取文档列表失败:', error)
    ElMessage.error('获取文档列表失败')
  } finally {
    docLoading.value = false
  }
}

// 前端过滤(关键字/所属项目/解析状态)
const filteredDocs = computed(() => {
  const { name, project_id, parse_status } = docQueryParams.value
  const kw = ((name as string) || '').trim().toLowerCase()
  return allDocs.value.filter(
    (d) =>
      (!kw || d.name.toLowerCase().includes(kw)) &&
      (!project_id || d.project_id === project_id) &&
      (!parse_status || d.parse_status === parse_status)
  )
})

// 当前页数据(前端分页)
const docPageData = computed(() => {
  const { page, size } = docPagination.value
  return filteredDocs.value.slice((page - 1) * size, page * size)
})

// 下载文档
const handleDocDownload = (row: ProjectDocument) => {
  window.open(getRagDocumentDownloadUrl(row.id), '_blank')
}

// 删除文档
const handleDocDelete = async (row: DocRow) => {
  try {
    await ElMessageBox.confirm(
      `确定删除文档"${row.name}"吗？物理文件与向量数据将一并删除。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    await deleteRagDocument(row.id)
    ElMessage.success('删除成功')
    allDocs.value = allDocs.value.filter((d) => d.id !== row.id)
  } catch (error) {
    console.log('取消删除或删除失败:', error)
  }
}

// 切到文档视图时按需加载
watch(viewMode, (mode) => {
  if (mode === 'documents' && allDocs.value.length === 0) {
    loadDocList()
  }
})

onMounted(() => {
  fetchData()
})

</script>
