<template>
  <div class="ocr-container">
    <h1 class="text-center mb-5 text-2xl font-bold">OCR 文字识别</h1>

    <!-- 文件上传和语言选择区域 -->
    <el-card class="mb-5">
      <div class="flex flex-col gap-4">
        <!-- 文件选择 -->
        <div class="flex items-center gap-3">
          <el-button type="primary" @click="triggerFileInput">
            选择图片 <span class="text-xs ml-1">支持拖拽</span>
          </el-button>
          <input
            ref="fileInputRef"
            type="file"
            class="hidden"
            accept="image/*"
            @change="handleFileChange"
          />
          <span v-if="targetFile" class="text-gray-600">{{ targetFile.name }}</span>
        </div>

        <!-- 识别语言选择 -->
        <div class="flex items-center gap-3">
          <span>识别语言:</span>
          <el-radio-group v-model="selectedLang">
            <el-radio
              v-for="lang in languages"
              :key="lang.code"
              :label="lang.code"
              border
            >
              {{ lang.name }}
            </el-radio>
          </el-radio-group>
          <el-button
            type="success"
            :loading="isProcessing"
            :disabled="!targetFile || isProcessing"
            @click="startRecognition"
          >
            {{ isProcessing ? '运行中...' : '开始识别' }}
          </el-button>
        </div>

        <!-- 翻译语言选择 -->
        <div class="flex items-center gap-3">
          <span>翻译语言:</span>
          <el-radio-group v-model="selectedLangTranslate">
            <el-radio
              v-for="lang in languages"
              :key="lang.code"
              :label="lang.code"
              border
            >
              {{ lang.name }}
            </el-radio>
          </el-radio-group>
          <el-button
            type="primary"
            :loading="isProcessing"
            :disabled="!targetFile || isProcessing"
            @click="startRecognitionTranslate"
          >
            {{ isProcessing ? '运行中...' : '识别+翻译' }}
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 结果展示区域 -->
    <div v-if="targetFile" class="flex flex-col lg:flex-row gap-5">
      <!-- 图片预览和检测结果 -->
      <el-card class="flex-1">
        <div class="font-bold mb-3">文 本 检 测 结 果</div>
        <div class="relative">
          <img
            :src="imageSrc"
            alt="目标图片"
            class="max-w-full hidden"
            @load="onImageLoad"
          />
          <canvas ref="canvasRef" class="max-w-full"></canvas>
          <div
            v-if="isProcessing"
            class="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30"
          >
            <el-icon class="is-loading text-white" size="48">
              <Loading /></el-icon>
          </div>
        </div>
      </el-card>

      <!-- 识别结果表格 -->
      <el-card class="flex-1">
        <div class="font-bold mb-3">
          文 本 识 别 结果
          <span v-if="processingTime"> (Total: {{ processingTime.toFixed(3) }}s)</span>
        </div>

        <div v-if="results.length" class="mb-3">
          <el-descriptions :column="3" size="small" border>
            <el-descriptions-item label="Det位置检测">{{ detectionTime.toFixed(3) }}s</el-descriptions-item>
            <el-descriptions-item label="Cls方向检测">{{ classificationTime.toFixed(3) }}s</el-descriptions-item>
            <el-descriptions-item label="Rec文字识别">{{ recognitionTime.toFixed(3) }}s</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-table
          v-if="results.length"
          :data="results"
          border
          stripe
          max-height="400"
        >
          <el-table-column prop="index" label="序号" width="60" />
          <el-table-column prop="text" label="识别结果" />
          <el-table-column prop="score" label="置信度" width="100">
            <template #default="{ row }">
              {{ row.score.toFixed(4) }}
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-else description="暂无识别结果" />
      </el-card>
    </div>

    <!-- 翻译背景图 -->
    <el-card v-if="bgImage" class="mt-5">
      <div class="font-bold mb-3">翻译背景图</div>
      <img
        :src="bgImage"
        alt="翻译背景图"
        class="w-full border border-gray-300 rounded"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import type { Language, OcrResult, OcrResponse } from '@/types/ocr'
import { fetchLanguages as fetchOCRLanguages, performOCR, performOCRWithTranslation } from '@/api/ocr'

// 响应式数据
const fileInputRef: Ref<HTMLInputElement | null> = ref(null)
const canvasRef: Ref<HTMLCanvasElement | null> = ref(null)
const ctx: Ref<CanvasRenderingContext2D | null> = ref(null)

const languages = ref<Language[]>([])
const selectedLang = ref('')
const selectedLangTranslate = ref('')

const targetFile = ref<File | null>(null)
const imageSrc = ref('')
const isProcessing = ref(false)
const results = ref<OcrResult[]>([])
const processingTime = ref(0)
const detectionTime = ref(0)
const classificationTime = ref(0)
const recognitionTime = ref(0)
const layout = ref<number[][]>([])
const bgImage = ref('')

let scale = 1

// 初始化
onMounted(() => {
  fetchLanguages()

  // 添加拖拽和粘贴事件监听
  document.addEventListener('dragover', handleDragOver)
  document.addEventListener('drop', handleDrop)
  document.addEventListener('paste', handlePaste)
})

// 组件卸载时移除事件监听
onUnmounted(() => {
  document.removeEventListener('dragover', handleDragOver)
  document.removeEventListener('drop', handleDrop)
  document.removeEventListener('paste', handlePaste)
})

// 获取支持的语言列表
const fetchLanguages = async () => {
  try {
    const data: Language[] = await fetchOCRLanguages()
    languages.value = data
    if (data.length > 0) {
      selectedLang.value = data[0].code
      selectedLangTranslate.value = data[0].code
    }
  } catch (error) {
    console.error('获取语言列表失败:', error)
    ElMessage.error('获取语言列表失败')
  }
}

// 触发文件选择
const triggerFileInput = () => {
  if (fileInputRef.value) {
    fileInputRef.value.click()
  }
}

// 处理文件选择
const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    // 清空之前的识别结果和画布内容
    clearPreviousResults()
    targetFile.value = target.files[0]
    previewImage(targetFile.value)
  }
}

// 处理拖拽事件
const handleDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const handleDrop = (e: DragEvent) => {
  e.preventDefault()
  if (e.dataTransfer && e.dataTransfer.files.length > 0) {
    // 清空之前的识别结果和画布内容
    clearPreviousResults()
    targetFile.value = e.dataTransfer.files[0]
    previewImage(targetFile.value)
  }
}

// 处理粘贴事件
const handlePaste = (e: ClipboardEvent) => {
  if (e.clipboardData && e.clipboardData.items) {
    const items = e.clipboardData.items
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === 'file') {
        // 清空之前的识别结果和画布内容
        clearPreviousResults()
        targetFile.value = items[i].getAsFile()
        if (targetFile.value) {
          previewImage(targetFile.value)
        }
        return
      }
    }
  }
}

// 清空之前的结果和画布
const clearPreviousResults = () => {
  // 清空识别结果
  results.value = []
  processingTime.value = 0
  detectionTime.value = 0
  classificationTime.value = 0
  recognitionTime.value = 0
  layout.value = []
  bgImage.value = ''

  // 清空画布
  if (canvasRef.value && ctx.value) {
    ctx.value.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  }
}

// 预览图片
const previewImage = (file: File) => {
  const reader = new FileReader()
  reader.onload = (e) => {
    imageSrc.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
}

// 图片加载完成事件
const onImageLoad = (e: Event) => {
  if (canvasRef.value) {
    const img = e.target as HTMLImageElement
    const naturalWidth = img.naturalWidth
    const naturalHeight = img.naturalHeight

    // 设置固定宽度
    const fixedWidth = 700

    // 计算缩放比例和高度
    scale = fixedWidth / naturalWidth
    const scaledHeight = (fixedWidth / naturalWidth) * naturalHeight

    // 设置canvas尺寸
    canvasRef.value.width = fixedWidth
    canvasRef.value.height = scaledHeight

    // 获取绘图上下文
    ctx.value = canvasRef.value.getContext('2d')
    if (ctx.value) {
      ctx.value.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)

      // 绘制缩放后的图片
      ctx.value.drawImage(img, 0, 0, fixedWidth, scaledHeight)

      // 重新绘制框线（如果有结果）
      if (results.value.length > 0 || layout.value.length > 0) {
        drawBoxes()
      }
    }
  }
}

// 绘制多边形框线
const drawPolyLines = (points: number[][]) => {
  if (!ctx.value) return

  ctx.value.moveTo(points[0][0], points[0][1])
  for (let i = 1; i < points.length; i++) {
    ctx.value.lineTo(points[i][0], points[i][1])
  }
  ctx.value.lineTo(points[0][0], points[0][1])
  ctx.value.stroke()
}

// 绘制识别框
const drawBoxes = () => {
  if (!ctx.value || !canvasRef.value) return

  ctx.value.strokeStyle = '#0000ff'
  ctx.value.font = '16px sans-serif'
  ctx.value.lineWidth = 1

  // 绘制文本框
  for (let i = 0; i < results.value.length; i++) {
    const result = results.value[i]
    // 调整坐标点按比例缩放
    const scaledBox = result.box.map(point => [point[0] * scale, point[1] * scale])
    drawPolyLines(scaledBox)

    // 绘制序号
    ctx.value.fillStyle = '#0000ff'
    ctx.value.fillText(i.toString(), scaledBox[0][0], scaledBox[0][1])
    ctx.value.strokeText(i.toString(), scaledBox[0][0], scaledBox[0][1])
  }

  // 绘制布局框
  ctx.value.strokeStyle = '#ff0000'
  ctx.value.fillStyle = '#ff0000'
  ctx.value.lineWidth = 1

  for (let i = 0; i < layout.value.length; i++) {
    const box = layout.value[i].map(point => point * scale)
    const [x1, y1, x2, y2] = box

    // 绘制矩形
    ctx.value.beginPath()
    ctx.value.moveTo(x1, y1)
    ctx.value.lineTo(x2, y1)
    ctx.value.lineTo(x2, y2)
    ctx.value.lineTo(x1, y2)
    ctx.value.closePath()
    ctx.value.stroke()

    // 绘制序号
    ctx.value.fillText(i.toString(), x1 + 5, y1 + 15)
  }
}

// 验证文件
const validateFile = (file: File): boolean => {
  // 检查文件类型
  const imageName = file.name
  const extName = imageName.split('.').pop()?.toLowerCase()
  const imgArr = ['webp', 'jpg', 'bmp', 'png', 'jpeg']

  if (!extName || !imgArr.includes(extName)) {
    ElMessage.error('图像文件格式不支持！')
    return false
  }

  // 检查文件大小
  const imageSize = file.size / 1024 / 1024
  if (imageSize >= 3) {
    ElMessage.error('图像大小超过3M!')
    return false
  }

  return true
}
const model_id = '2229c9a3fcc54d1d83d0636a7398b62e'
// 开始识别
const startRecognition = async () => {
  if (!targetFile.value) return

  if (!validateFile(targetFile.value)) return

  const formData = new FormData()
  formData.append('image', targetFile.value)
  formData.append('lang', selectedLang.value)
  formData.append('model_id', model_id)


  isProcessing.value = true
  results.value = []
  processingTime.value = 0
  detectionTime.value = 0
  classificationTime.value = 0
  recognitionTime.value = 0
  layout.value = []
  bgImage.value = ''

  try {
    const data: OcrResponse = await performOCR(formData)

    // 处理结果
    results.value = (data.results || []).map((item, index) => ({
      ...item,
      index
    }))

    processingTime.value = data.ts?.total || 0
    detectionTime.value = (data.ts?.detect || 0) + (data.ts?.['post-detect'] || 0)
    classificationTime.value = (data.ts?.classify || 0) + (data.ts?.['post-classify'] || 0)
    recognitionTime.value = (data.ts?.recognize || 0) + (data.ts?.['post-recognize'] || 0)
    layout.value = data.layout || []

    // 绘制框线
    if (canvasRef.value && ctx.value) {
      drawBoxes()
    }
  } catch (error) {
    console.error('识别失败:', error)
    ElMessage.error('识别失败: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    isProcessing.value = false
  }
}

// 开始识别并翻译
const startRecognitionTranslate = async () => {
  if (!targetFile.value) return

  if (!validateFile(targetFile.value)) return

  const formData = new FormData()
  formData.append('image', targetFile.value)
  formData.append('model_id', model_id)
  formData.append('lang_ocr', selectedLang.value)
  formData.append('lang_translate', selectedLangTranslate.value)

  debugger
  isProcessing.value = true
  results.value = []
  processingTime.value = 0
  detectionTime.value = 0
  classificationTime.value = 0
  recognitionTime.value = 0
  layout.value = []
  bgImage.value = ''

  try {
    const data: OcrResponse = await performOCRWithTranslation(formData)

    // 处理结果
    results.value = (data.results || []).map((item, index) => ({
      ...item,
      index
    }))

    processingTime.value = data.ts?.total || 0
    detectionTime.value = (data.ts?.detect || 0) + (data.ts?.['post-detect'] || 0)
    classificationTime.value = (data.ts?.classify || 0) + (data.ts?.['post-classify'] || 0)
    recognitionTime.value = (data.ts?.recognize || 0) + (data.ts?.['post-recognize'] || 0)
    layout.value = data.layout || []

    // 绘制框线
    if (canvasRef.value && ctx.value) {
      drawBoxes()
    }

    // 设置背景图
    if (data.background) {
      bgImage.value = `data:image/jpeg;base64,${data.background}`
    }
  } catch (error) {
    console.error('识别+翻译失败:', error)
    ElMessage.error('识别+翻译失败: ' + (error instanceof Error ? error.message : '未知错误'))
  } finally {
    isProcessing.value = false
  }
}
</script>

<style scoped>
.ocr-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

:deep(.el-card) {
  --el-card-padding: 20px;
}
</style>
