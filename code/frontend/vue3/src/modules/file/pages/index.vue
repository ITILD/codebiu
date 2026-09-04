<template>
  <div p-2 w-full flex flex-col h-app>
    <!-- 工具栏 -->
    <div mb-3 flex flex-wrap items-center gap-2>
      <el-tooltip content="返回上级" placement="top">
        <el-button :icon="Back" :disabled="!currentPid" @click="handleUp" />
      </el-tooltip>
      <el-breadcrumb separator="/" flex-1 min-w-0>
        <el-breadcrumb-item>
          <span cursor-pointer hover:text-blue-5 @click="handleGoto(-1)">根目录</span>
        </el-breadcrumb-item>
        <el-breadcrumb-item v-for="(crumb, idx) in breadcrumbs" :key="crumb.id">
          <span cursor-pointer hover:text-blue-5 @click="handleGoto(idx)">{{ crumb.name }}</span>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <el-input
        class="w-full sm:w-56"
        v-model="searchQuery"
        placeholder="按名称搜索"
        clearable
        :prefix-icon="Search"
        @input="handleSearchDebounced"
        @clear="handleSearchDebounced"
      />
      <el-button :icon="FolderAdd" @click="handleCreateFolder" :disabled="loading">新建目录</el-button>
      <el-upload :show-file-list="false" :before-upload="handleUpload" :disabled="uploading" multiple>
        <el-button type="primary" :loading="uploading" :icon="Upload">
          {{ uploading ? '上传中' : '上传文件' }}
        </el-button>
      </el-upload>
    </div>

    <!-- 目录内容表格 -->
    <el-table
      v-loading="loading"
      :data="entries"
      stripe
      flex-1
      @row-dblclick="handleOpen"
    >
      <el-table-column label="名称" min-width="260" show-overflow-tooltip>
        <template #default="{ row }">
          <div flex items-center gap-2 cursor-pointer @click="handleOpen(row)">
            <el-icon text-lg :class="row.is_directory ? 'text-amber-5' : fileIconClass(row.file_extension)">
              <Folder v-if="row.is_directory" />
              <Document v-else />
            </el-icon>
            <span>{{ row.name }}</span>
            <el-tag v-if="row.is_directory" size="small" type="warning" effect="plain">目录</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="110" align="center">
        <template #default="{ row }">
          {{ row.is_directory ? '-' : formatSize(row.file_size_bytes) }}
        </template>
      </el-table-column>
      <el-table-column label="类型" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="!row.is_directory" size="small" type="info">
            {{ (row.file_extension || 'file').toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.description || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="修改时间" width="120" align="center">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="270" align="center" fixed="right">
        <template #default="{ row }">
          <el-button v-if="!row.is_directory" size="small" type="primary" plain @click="handleDownload(row)">
            下载
          </el-button>
          <el-button size="small" type="success" plain @click="handleMove(row)">移动</el-button>
          <el-button size="small" type="warning" plain @click="handleEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 空状态提示 -->
    <div v-if="!loading && entries.length === 0" py-10 flex flex-col items-center text-gray-4>
      <el-icon text-5xl mb-3><FolderOpened /></el-icon>
      <p m-0>{{ searchQuery ? '未找到匹配的条目' : '当前目录为空，可上传文件或新建目录' }}</p>
    </div>

    <!-- 分页(手机居中, 桌面靠右) -->
    <div mt-3 flex flex-wrap justify-center sm:justify-end>
      <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.size"
        :total="total" layout="total, prev, pager, next"
        @size-change="fetchData" @current-change="fetchData" />
    </div>

    <!-- 新建目录对话框 -->
    <el-dialog v-model="folderDialogVisible" title="新建目录" width="90%" class="max-w-[420px]">
      <el-form :model="folderForm" :rules="nameRules" ref="folderFormRef" label-width="80px" @submit.prevent>
        <el-form-item label="目录名" prop="name">
          <el-input v-model="folderForm.name" placeholder="请输入目录名" maxlength="255" @keyup.enter="handleFolderSubmit" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="folderDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleFolderSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 编辑条目对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑条目" width="90%" class="max-w-[420px]">
      <el-form :model="editForm" :rules="nameRules" ref="editFormRef" label-width="80px" @submit.prevent>
        <el-form-item label="名称" prop="name">
          <el-input v-model="editForm.name" placeholder="请输入名称" maxlength="255" @keyup.enter="handleEditSubmit" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="请输入描述" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="editDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleEditSubmit" :loading="submitting">确认</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 移动条目对话框(目录树懒加载) -->
    <el-dialog v-model="moveDialogVisible" title="移动到指定目录" width="90%" class="max-w-[460px]">
      <el-alert
        v-if="moveEntryData"
        :title="`将移动「${moveEntryData.name}」${moveEntryData.is_directory ? '及其全部子项' : ''}到所选目录`"
        type="info"
        :closable="false"
        mb-3
      />
      <el-tree
        v-if="moveDialogVisible"
        ref="moveTreeRef"
        :data="moveTreeData"
        :props="treeProps"
        node-key="id"
        lazy
        highlight-current
        :load="loadTreeNodes"
        :expand-on-click-node="false"
        @node-click="handleTreeNodeClick"
        class="max-h-[320px] overflow-auto border rounded"
      >
        <template #default="{ node, data }">
          <span flex items-center gap-1>
            <el-icon text-amber-5><Folder /></el-icon>
            <span>{{ node.label }}</span>
            <el-tag v-if="data.is_root" size="small" type="success" effect="plain">根目录</el-tag>
          </span>
        </template>
      </el-tree>
      <template #footer>
        <span>
          <el-button @click="moveDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleMoveSubmit" :loading="submitting">
            移动到「{{ moveTargetName || '根目录' }}」
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import {
  Back,
  Upload,
  FolderAdd,
  Folder,
  Document,
  FolderOpened,
  Search,
} from '@element-plus/icons-vue'
import {
  listDir,
  listDirs,
  uploadFile,
  createFolder,
  getFileDownloadUrl,
  updateFileEntry,
  moveEntry,
  deleteFile,
  deleteFolder,
} from '@/api/file/filesystem'
import type { FileEntry } from '@/types/file'
import type { PaginationParams } from '@/types/common'
import { ElMessage, ElMessageBox, type FormInstance, type TreeInstance } from 'element-plus'

// 面包屑目录栈(从根到当前目录)
const breadcrumbs = ref<{ id: string; name: string }[]>([])
// 当前目录ID(空表示根目录)
const currentPid = computed(() =>
  breadcrumbs.value.length ? breadcrumbs.value[breadcrumbs.value.length - 1].id : undefined
)

// 列表数据
const entries = ref<FileEntry[]>([])
const loading = ref(false)
const uploading = ref(false)
const submitting = ref(false)
const searchQuery = ref('')
const total = ref(0)
const pagination = ref<PaginationParams>({ page: 1, size: 50 })

// 目录树节点(移动对话框用)
type TreeNode = {
  id: string
  name: string
  is_root?: boolean
  leaf?: boolean
}

// 名称校验规则
const nameRules = {
  name: [
    { required: true, message: '请输入名称', trigger: 'blur' },
    { pattern: /^[^/\\:*?"<>|]+$/, message: '名称不能包含 / \\ : * ? " < > | 字符', trigger: 'blur' },
  ],
}

// 文件图标按扩展名着色
const fileIconClass = (ext: string) => {
  const e = (ext || '').toLowerCase()
  if (['pdf'].includes(e)) return 'text-red-5'
  if (['doc', 'docx'].includes(e)) return 'text-blue-5'
  if (['xls', 'xlsx', 'csv'].includes(e)) return 'text-green-5'
  if (['ppt', 'pptx'].includes(e)) return 'text-orange-5'
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(e)) return 'text-purple-5'
  if (['zip', 'rar', '7z', 'tar', 'gz'].includes(e)) return 'text-yellow-6'
  return 'text-gray-5'
}

// 文件大小格式化
const formatSize = (bytes: number) => {
  if (!bytes) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

// 日期格式化
const formatDate = (value: string) => new Date(value).toLocaleDateString()

// 获取当前目录内容(服务端名称过滤)
const fetchData = async () => {
  try {
    loading.value = true
    const res = await listDir(currentPid.value, pagination.value, searchQuery.value.trim() || undefined)
    entries.value = res.items
    total.value = res.total
  } catch (error) {
    console.error('获取目录内容失败:', error)
    ElMessage.error('获取目录内容失败')
  } finally {
    loading.value = false
  }
}

// 搜索防抖(300ms)
let searchTimer: ReturnType<typeof setTimeout> | undefined
const handleSearchDebounced = () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    pagination.value.page = 1
    fetchData()
  }, 300)
}

// 打开条目(目录进入,文件忽略)
const handleOpen = (row: FileEntry) => {
  if (!row.is_directory) return
  breadcrumbs.value.push({ id: row.id, name: row.name })
  pagination.value.page = 1
  fetchData()
}

// 面包屑跳转(-1 表示根目录)
const handleGoto = (idx: number) => {
  breadcrumbs.value = breadcrumbs.value.slice(0, idx + 1)
  pagination.value.page = 1
  fetchData()
}

// 返回上级目录
const handleUp = () => {
  if (!breadcrumbs.value.length) return
  breadcrumbs.value.pop()
  pagination.value.page = 1
  fetchData()
}

// 上传文件(返回 false 阻止 el-upload 默认行为)
const handleUpload = async (file: File) => {
  try {
    uploading.value = true
    await uploadFile(file, currentPid.value)
    ElMessage.success(`文件"${file.name}"上传成功`)
    fetchData()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error(`文件"${file.name}"上传失败`)
  } finally {
    uploading.value = false
  }
  return false
}

// 下载文件(新窗口触发后端下载流)
const handleDownload = (row: FileEntry) => {
  window.open(getFileDownloadUrl(row.id), '_blank')
}

// ---------------- 新建目录 ----------------
const folderDialogVisible = ref(false)
const folderFormRef = ref<FormInstance>()
const folderForm = reactive({ name: '' })

const handleCreateFolder = () => {
  folderForm.name = ''
  folderDialogVisible.value = true
}

const handleFolderSubmit = async () => {
  if (!folderFormRef.value) return
  const valid = await folderFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await createFolder(folderForm.name.trim(), currentPid.value)
    ElMessage.success('目录创建成功')
    folderDialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('创建目录失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '创建目录失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 编辑条目 ----------------
const editDialogVisible = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive({ name: '', description: '' })
const currentEntry = ref<FileEntry | null>(null)

const handleEdit = (row: FileEntry) => {
  currentEntry.value = row
  Object.assign(editForm, { name: row.name, description: row.description || '' })
  editDialogVisible.value = true
}

const handleEditSubmit = async () => {
  if (!editFormRef.value || !currentEntry.value) return
  const valid = await editFormRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    submitting.value = true
    await updateFileEntry(currentEntry.value.id, {
      name: editForm.name.trim(),
      description: editForm.description,
    })
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('更新失败:', error)
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

// ---------------- 移动条目(目录树懒加载) ----------------
const moveDialogVisible = ref(false)
const moveTreeRef = ref<TreeInstance>()
const moveEntryData = ref<FileEntry | null>(null)
const moveTreeData = ref<TreeNode[]>([])
const moveTargetPid = ref<string | undefined>(undefined)
const moveTargetName = ref('')

const treeProps = {
  label: 'name',
  children: 'children',
  isLeaf: 'leaf',
}

// 打开移动对话框(重置目录树并默认选中根目录)
const handleMove = async (row: FileEntry) => {
  moveEntryData.value = row
  moveTargetPid.value = undefined
  moveTargetName.value = '根目录'
  moveTreeData.value = [
    { id: '__root__', name: '根目录', is_root: true, leaf: false },
  ]
  moveDialogVisible.value = true
  // 树渲染完成后展开并选中根目录节点
  await nextTick()
  moveTreeRef.value?.setCurrentKey('__root__')
  moveTreeRef.value?.getNode('__root__')?.expand()
}

// 懒加载目录树节点(根目录虚拟节点加载根级子目录)
// 参数类型与 el-tree 的 load 签名保持宽松兼容(node.data 为动态数据)
const loadTreeNodes = async (
  node: { data: Record<string, any> },
  resolve: (children: any[]) => void
) => {
  try {
    // 根目录虚拟节点 → 查询根级目录;其他节点按 id 查询子目录
    const pid = node.data.is_root ? undefined : node.data.id
    const dirs = await listDirs(pid)
    resolve(
      dirs.map((d) => ({
        id: d.id,
        name: d.name,
        leaf: false,
      }))
    )
  } catch (error) {
    console.error('加载目录树失败:', error)
    ElMessage.error('加载目录树失败')
    resolve([])
  }
}

// 树节点点击选中目标目录(更新移动目标)
const handleTreeNodeClick = (data: TreeNode) => {
  // 防护: 不可移动到条目自身(后端还有子孙环形引用校验)
  if (moveEntryData.value && data.id === moveEntryData.value.id) {
    ElMessage.warning('不能移动到自身目录')
    return
  }
  moveTargetPid.value = data.is_root ? undefined : data.id
  moveTargetName.value = data.name
}

// 提交移动(使用点击选中的目标目录)
const handleMoveSubmit = async () => {
  if (!moveEntryData.value) return
  try {
    submitting.value = true
    await moveEntry(moveEntryData.value.id, moveTargetPid.value)
    ElMessage.success(`已移动到「${moveTargetName.value || '根目录'}」`)
    moveDialogVisible.value = false
    fetchData()
  } catch (error) {
    console.error('移动失败:', error)
    ElMessage.error(error instanceof Error ? error.message : '移动失败')
  } finally {
    submitting.value = false
  }
}

// 删除条目(目录递归删除)
const handleDelete = async (row: FileEntry) => {
  try {
    await ElMessageBox.confirm(
      row.is_directory
        ? `确定删除目录"${row.name}"吗？目录下全部内容将一并删除。`
        : `确定删除文件"${row.name}"吗？`,
      '警告',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
    if (row.is_directory) {
      await deleteFolder(row.id)
    } else {
      await deleteFile(row.id)
    }
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
