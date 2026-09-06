<template>
  <div class="w-full max-w-[1400px] mx-auto flex flex-col gap-4 p-2 md:p-4">
    <!-- 页头 -->
    <div class="bg-note-card rounded-xl shadow-note border border-note p-4 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="bg-note-tint rounded-lg p-2 flex-center">
          <el-icon :size="22" class="text-note-green"><Camera /></el-icon>
        </div>
        <div>
          <h1 class="text-base md:text-lg font-semibold text-note">MediaPipe 人脸特征实验台</h1>
          <p class="text-xs md:text-sm text-note-sub mt-0.5">相机特征点检测 · BabylonJS 三维网格 · 特征向量余弦相似度</p>
        </div>
      </div>
      <div class="flex items-center gap-2 text-xs">
        <span class="bg-note-tint text-note-green rounded-full px-3 py-1">fps {{ fps.toFixed(1) }}</span>
        <span class="rounded-full px-3 py-1" :class="statusClass">{{ statusText }}</span>
      </div>
    </div>

    <!-- 相机预览 + 特征网格叠加(共用一个画面) -->
    <div class="bg-note-card rounded-xl shadow-note border border-note p-4 flex flex-col gap-3">
      <div class="flex items-center justify-between flex-wrap gap-2">
        <div class="flex items-center gap-2 text-note font-medium text-sm">
          <el-icon><VideoCamera /></el-icon> 相机预览 · 特征网格叠加
        </div>
        <div class="flex items-center gap-2">
          <el-radio-group v-model="renderMode" size="small">
            <el-radio-button value="solid">实体</el-radio-button>
            <el-radio-button value="wire">线框</el-radio-button>
            <el-radio-button value="points">点云</el-radio-button>
          </el-radio-group>
          <el-button size="small" :icon="RefreshRight" @click="resetView">复位</el-button>
          <el-button size="small" text bg :icon="Refresh" @click="refreshDevices">刷新设备</el-button>
        </div>
      </div>
      <div class="mx-auto w-full max-w-[720px]">
        <div
          id="previewP"
          class="relative w-full rounded-lg overflow-hidden bg-note-soft border border-note"
          :style="{ aspectRatio: String(videoAspect) }"
        >
          <video id="videoDom" playsinline muted class="absolute inset-0 w-full h-full object-cover -scale-x-100"></video>
          <!-- 3D 网格叠加层: 正交投影与画面同尺映射, 默认像素级贴合人脸 -->
          <canvas id="meshDom" class="absolute inset-0 w-full h-full block touch-none"></canvas>
          <!-- 状态遮罩 -->
          <div
            v-if="status !== 'running'"
            class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-note-sub text-sm bg-[rgba(244,248,242,0.75)] dark:bg-[rgba(13,23,17,0.75)]"
          >
            <el-icon :size="28" :class="{ 'animate-spin': status === 'loading' }"><Loading /></el-icon>
            <span>{{ status === 'error' ? errorMsg : '正在初始化模型与摄像头…' }}</span>
          </div>
        </div>
        <p class="text-xs text-note-sub mt-2">
          网格默认贴合人脸画面 · 拖动旋转/滚轮缩放自由查看三维 · 复位恢复贴合 · 橙色为五官轮廓(眼/眉/唇/脸缘)
        </p>
      </div>
      <!-- 相机选择 -->
      <el-select
        v-model="deviceId"
        placeholder="选择相机设备"
        class="mx-auto w-full max-w-[720px]"
        :disabled="deviceOptions.length === 0"
        @change="switchCamera"
      >
        <el-option
          v-for="d in deviceOptions"
          :key="d.deviceId"
          :label="d.label || `相机 ${d.deviceId.slice(-4)}`"
          :value="d.deviceId"
        />
      </el-select>
    </div>

    <!-- MediaPipe 检测选项 -->
    <div class="bg-note-card rounded-xl shadow-note border border-note p-4">
      <div class="flex items-center gap-2 text-note font-medium text-sm mb-3">
        <el-icon><Setting /></el-icon> MediaPipe 检测选项
        <span class="text-xs text-note-sub font-normal">切换后自动应用(部分选项会触发模型重建)</span>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-x-6 gap-y-4">
        <div class="flex items-center justify-between gap-2">
          <div>
            <div class="text-sm text-note">表情系数</div>
            <div class="text-xs text-note-sub">输出 52 维 blendshapes</div>
          </div>
          <el-switch v-model="optBlendshapes" @change="applyOptions" />
        </div>
        <div class="flex items-center justify-between gap-2">
          <div>
            <div class="text-sm text-note">头部姿态矩阵</div>
            <div class="text-xs text-note-sub">输出变换矩阵(位置/朝向)</div>
          </div>
          <el-switch v-model="optMatrix" @change="applyOptions" />
        </div>
        <div class="flex items-center justify-between gap-2">
          <div>
            <div class="text-sm text-note">推理后端</div>
            <div class="text-xs text-note-sub">GPU 加速失败时可切换 CPU</div>
          </div>
          <el-radio-group v-model="optDelegate" size="small" @change="applyOptions">
            <el-radio-button value="GPU">GPU</el-radio-button>
            <el-radio-button value="CPU">CPU</el-radio-button>
          </el-radio-group>
        </div>
        <div>
          <div class="flex items-center justify-between">
            <div class="text-sm text-note">最大人脸数</div>
            <span class="text-xs text-note-sub">{{ optNumFaces }}</span>
          </div>
          <el-slider v-model="optNumFaces" :min="1" :max="4" :step="1" @change="applyOptions" />
        </div>
      </div>
    </div>

    <!-- 特征向量对比 -->
    <div class="bg-note-card rounded-xl shadow-note border border-note p-4">
      <div class="flex items-center gap-2 text-note font-medium text-sm mb-1">
        <el-icon><DataAnalysis /></el-icon> 标准化特征向量与人脸匹配
        <span class="text-xs text-note-sub font-normal">
          由 <code class="text-note-green">api/face.ts</code> 提取(L2 归一化) · 余弦相似度判定
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-2 my-3">
        <el-button color="#6b9e78" :disabled="status !== 'running'" @click="captureFeature('A')">捕获当前帧为特征 A</el-button>
        <el-button color="#e07a5f" :disabled="status !== 'running'" @click="captureFeature('B')">捕获当前帧为特征 B</el-button>
        <el-button text :disabled="!featureA && !featureB" @click="clearFeatures">清除</el-button>
        <div class="ml-auto flex items-center gap-2 text-xs text-note-sub">
          匹配阈值 ≥ {{ matchThreshold.toFixed(2) }}
          <el-slider v-model="matchThreshold" :min="0.5" :max="1" :step="0.01" class="w-40" />
        </div>
      </div>
      <!-- A/B 特征卡片 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div
          v-for="slot in (['A', 'B'] as const)"
          :key="slot"
          class="bg-note-soft rounded-lg border border-note p-3 flex flex-col gap-2 min-h-[96px]"
        >
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-note">特征 {{ slot }}</span>
            <el-tag v-if="featureSlot(slot)" size="small" type="success" effect="plain">dim {{ featureSlot(slot)!.dim }}</el-tag>
          </div>
          <template v-if="featureSlot(slot)">
            <div class="text-xs text-note-sub text-ellipsis">{{ featureSlot(slot)!.version }} · {{ featureSlot(slot)!.source }}</div>
            <div class="flex flex-wrap gap-1 items-center">
              <span
                v-for="(v, i) in featureSlot(slot)!.data.slice(0, 6)"
                :key="i"
                class="text-[10px] bg-note-tint text-note-green rounded px-1.5 py-0.5"
              >
                {{ v.toFixed(3) }}
              </span>
              <span class="text-[10px] text-note-sub">… 共 {{ featureSlot(slot)!.dim }} 维</span>
            </div>
          </template>
          <div v-else class="text-xs text-note-sub">点击上方按钮捕获当前人脸特征</div>
        </div>
      </div>
      <!-- 相似度结果 -->
      <div v-if="compareResult" class="mt-4 bg-note-tint rounded-lg p-3 border border-note-green">
        <div class="flex items-center justify-between mb-2 flex-wrap gap-2">
          <div class="flex items-center gap-2 text-sm text-note">
            余弦相似度
            <span class="text-lg font-semibold" :class="compareResult.matched ? 'text-note-green' : 'text-[#e07a5f]'">
              {{ compareResult.similarity.toFixed(4) }}
            </span>
            <el-tag :type="compareResult.matched ? 'success' : 'warning'" size="small" effect="plain">
              {{ compareResult.matched ? '判定为同一人' : '未达匹配阈值' }}
            </el-tag>
          </div>
          <span class="text-xs text-note-sub">距离 {{ compareResult.distance.toFixed(4) }} · 阈值 {{ matchThreshold.toFixed(2) }}</span>
        </div>
        <el-progress :percentage="similarityPercent" :color="compareResult.matched ? '#6b9e78' : '#e07a5f'" :stroke-width="10" />
      </div>
    </div>

    <!-- 表情系数 -->
    <div class="bg-note-card rounded-xl shadow-note border border-note p-4">
      <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div class="flex items-center gap-2 text-note font-medium text-sm">
          <el-icon><MagicStick /></el-icon> 表情系数 (Blendshapes)
        </div>
        <span class="text-xs text-note-sub">共 {{ categories.length }} 项 · 特征向量的数据来源</span>
      </div>
      <div v-if="categories.length === 0" class="text-xs text-note-sub py-4 text-center">
        暂无数据 — 请开启摄像头并让人脸入镜(若已入镜请检查上方"表情系数"开关)
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-2">
        <div v-for="c in categories" :key="c.categoryName" class="bg-note-soft rounded px-2 py-1.5 border border-note">
          <div class="flex items-center justify-between gap-1">
            <span class="text-xs text-note text-ellipsis">{{ c.categoryName }}</span>
            <span class="text-[10px] text-note-sub">{{ c.score.toFixed(2) }}</span>
          </div>
          <div class="mt-1 h-1 rounded-full bg-note-tint overflow-hidden">
            <div
              class="h-full bg-note-green rounded-full transition-all duration-150"
              :style="{ width: `${Math.min(100, c.score * 100)}%` }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed, watch } from 'vue'
import { FilesetResolver, FaceLandmarker, type FaceLandmarkerResult } from '@mediapipe/tasks-vision'
import {
  Camera, VideoCamera, Refresh, RefreshRight, Loading, Setting, DataAnalysis, MagicStick,
} from '@element-plus/icons-vue'
import { FaceMeshScene, type FaceMeshRenderMode } from '../utils/FaceMeshScene'
import {
  extractFaceFeature, compareFaceFeatures,
  type FaceBlendshapeCategory, type FaceFeatureVector, type FaceCompareResult,
} from '../api/face'

// ===== 运行状态 =====
type Status = 'loading' | 'running' | 'error'
const status = ref<Status>('loading')
const errorMsg = ref('')
const fps = ref(0)
const statusText = computed(() => ({ loading: '初始化中…', running: '检测运行中', error: '运行出错' })[status.value])
const statusClass = computed(() =>
  status.value === 'running'
    ? 'bg-note-tint text-note-green'
    : 'bg-[#f7eaea] text-[#c26d6d] dark:bg-[#3a2626] dark:text-[#d99c9c]'
)

// ===== 相机 =====
const deviceOptions = ref<{ deviceId: string; label: string }[]>([])
const deviceId = ref('')
/** 视频宽高比(容器与视频流保持一致, 避免 object-cover 裁剪导致网格错位; 缺省 4:3) */
const videoAspect = ref(4 / 3)

// ===== MediaPipe 检测选项 =====
const optBlendshapes = ref(true)
const optMatrix = ref(true)
const optDelegate = ref<'GPU' | 'CPU'>('GPU')
const optNumFaces = ref(1)

// ===== 3D 展示 =====
const renderMode = ref<FaceMeshRenderMode>('solid')

// ===== 检测结果 =====
const categories = ref<FaceBlendshapeCategory[]>([])

// ===== 特征向量对比 =====
const featureA = ref<FaceFeatureVector | null>(null)
const featureB = ref<FaceFeatureVector | null>(null)
const matchThreshold = ref(0.92)
const compareResult = computed<FaceCompareResult | null>(() =>
  featureA.value && featureB.value
    ? compareFaceFeatures(featureA.value, featureB.value, matchThreshold.value)
    : null
)
const similarityPercent = computed(() => {
  const s = compareResult.value?.similarity
  return s === undefined ? 0 : Math.round(Math.max(0, Math.min(1, s)) * 1000) / 10
})
/** 取 A/B 槽位特征 */
function featureSlot(slot: 'A' | 'B') {
  return slot === 'A' ? featureA.value : featureB.value
}

// ===== 内部对象 =====
let faceLandmarker: FaceLandmarker | undefined
let meshScene: FaceMeshScene | undefined
let video: HTMLVideoElement
let stream: MediaStream | undefined
let running = false

// fps 统计
class FpsShow {
  private fpsVal = 0
  private startTime = Date.now()
  private frameCount = 0
  update() {
    this.frameCount++
    const elapsed = Date.now() - this.startTime
    if (elapsed >= 1000) {
      this.fpsVal = this.frameCount / (elapsed / 1000)
      this.startTime = Date.now()
      this.frameCount = 0
    }
  }
  getFps() {
    return this.fpsVal
  }
}
const fpsShow = new FpsShow()

// ===== 初始化 =====
onMounted(async () => {
  try {
    // 1 加载 MediaPipe 人脸模型
    faceLandmarker = await loadMediapipeModels()
    // 2 初始化 Babylon 特征网格场景
    initMeshScene()
    // 3 开启摄像头(默认设备)并进入帧循环
    await openCamera()
    // 4 枚举相机设备(授权后才能读到 label)
    await refreshDevices()
    status.value = 'running'
  } catch (e) {
    status.value = 'error'
    errorMsg.value = `初始化失败: ${e instanceof Error ? e.message : e}`
  }
})

onBeforeUnmount(() => {
  running = false
  stopStream()
  meshScene?.dispose()
  meshScene = undefined
  faceLandmarker?.close()
  faceLandmarker = undefined
})

/**
 * 1 加载 MediaPipe FaceLandmarker 模型(本地 jsLib 资源)
 */
async function loadMediapipeModels() {
  const vision = await FilesetResolver.forVisionTasks('/jsLib/mediapipe/tasks-vision-0.10.17/wasm')
  const landmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: '/jsLib/mediapipe/face_landmarker.task',
      delegate: optDelegate.value,
    },
    runningMode: 'VIDEO',
    outputFaceBlendshapes: optBlendshapes.value,
    outputFacialTransformationMatrixes: optMatrix.value,
    numFaces: optNumFaces.value,
  })
  return landmarker
}

/**
 * 2 初始化 Babylon 人脸网格场景(网格拓扑来自 MediaPipe 静态常量)
 */
function initMeshScene() {
  meshScene = new FaceMeshScene('meshDom')
  meshScene.initMesh(FaceLandmarker.FACE_LANDMARKS_TESSELATION, FaceLandmarker.FACE_LANDMARKS_CONTOURS)
  meshScene.observeInit('previewP')
  meshScene.setRenderMode(renderMode.value)
  // 开发模式暴露调试句柄, 便于控制台注入合成特征点验证渲染
  if (import.meta.env.DEV) {
    ;(window as any).__faceMeshScene = meshScene
  }
}

// 渲染模式切换
watch(renderMode, (mode) => meshScene?.setRenderMode(mode))

/**
 * 3 开启摄像头视频流并进入 requestVideoFrameCallback 帧循环
 * @param id 指定设备 ID(切换相机时); 缺省用 facingMode: user
 */
async function openCamera(id?: string) {
  stopStream()
  const videoConfig: MediaTrackConstraints = {
    facingMode: 'user',
    width: { ideal: 640 },
    height: { ideal: 480 },
  }
  if (id) videoConfig.deviceId = { exact: id }
  stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: videoConfig })
  video = document.getElementById('videoDom') as HTMLVideoElement
  video.srcObject = stream
  await video.play()
  // 容器宽高比跟随实际视频流, 保证网格与画面同尺映射
  if (video.videoWidth && video.videoHeight) {
    videoAspect.value = video.videoWidth / video.videoHeight
  }
  // 帧循环只注册一次, 切换相机时随视频元素自动继续
  if (!running) {
    running = true
    video.requestVideoFrameCallback(onVideoFrame)
  }
}

/** 停止当前视频流 */
function stopStream() {
  stream?.getTracks().forEach((t) => t.stop())
  stream = undefined
}

/** 切换相机设备 */
async function switchCamera(id: string) {
  try {
    await openCamera(id)
  } catch (e) {
    ElMessage.error(`切换相机失败: ${e instanceof Error ? e.message : e}`)
    await refreshDevices()
  }
}

/** 枚举相机设备并同步当前选中项 */
async function refreshDevices() {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    deviceOptions.value = devices
      .filter((d) => d.kind === 'videoinput')
      .map((d) => ({ deviceId: d.deviceId, label: d.label }))
    const current = stream?.getVideoTracks()[0]?.getSettings().deviceId
    if (current) deviceId.value = current
    else if (!deviceId.value && deviceOptions.value.length) deviceId.value = deviceOptions.value[0].deviceId
  } catch (e) {
    console.warn('枚举相机设备失败:', e)
  }
}

/**
 * 应用检测选项变更(setOptions 内部按需重建模型图)
 */
async function applyOptions() {
  if (!faceLandmarker) return
  try {
    await faceLandmarker.setOptions({
      baseOptions: {
        delegate: optDelegate.value,
      },
      outputFaceBlendshapes: optBlendshapes.value,
      outputFacialTransformationMatrixes: optMatrix.value,
      numFaces: optNumFaces.value,
    })
  } catch (e) {
    ElMessage.error(`选项应用失败: ${e instanceof Error ? e.message : e}`)
  }
}

/**
 * 帧循环: 检测 -> 更新 3D 网格与表情系数 -> 统计 fps
 * 先注册下一帧再检测, 保证检测异常不会中断帧循环
 */
function onVideoFrame(time: number) {
  if (!running) return
  video.requestVideoFrameCallback(onVideoFrame)
  detectFrame(time)
  fpsShow.update()
  fps.value = fpsShow.getFps()
}

/**
 * 单帧检测: 更新 3D 网格 / 表情系数
 */
function detectFrame(time: number) {
  if (!faceLandmarker || video.readyState < 2) return
  let result: FaceLandmarkerResult
  try {
    result = faceLandmarker.detectForVideo(video, time)
  } catch {
    return // setOptions 重建模型图瞬间可能抛错, 跳过该帧
  }
  // 3D 特征网格(取第一张脸)
  try {
    meshScene?.updateLandmarks(result.faceLandmarks?.[0] ?? [])
  } catch (e) {
    console.warn('3D 网格更新异常:', e)
  }
  // 表情系数
  const blendshapes = result.faceBlendshapes?.[0]?.categories
  if (blendshapes) categories.value = blendshapes as FaceBlendshapeCategory[]
}

/** 复位三维视角 */
function resetView() {
  meshScene?.resetView()
}

/**
 * 捕获当前帧标准化特征向量到 A/B 槽位
 */
function captureFeature(slot: 'A' | 'B') {
  const feature = extractFaceFeature(categories.value, `摄像头帧 @ ${new Date().toLocaleTimeString()}`)
  if (!feature) {
    ElMessage.warning('未捕获到人脸特征(请确认人脸已入镜且"表情系数"开关已开启)')
    return
  }
  if (slot === 'A') featureA.value = feature
  else featureB.value = feature
  ElMessage.success(`已捕获特征 ${slot} (dim=${feature.dim})`)
}

/** 清除 A/B 特征 */
function clearFeatures() {
  featureA.value = null
  featureB.value = null
}
</script>
