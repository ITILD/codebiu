<template>
  <div flex flex-col w-full bg-gray-50 p-2 md:p-4>
    <div flex flex-col md:flex-row gap-4>
      <video id="videoDom" width="500" height="500" -scale-x-100 class="w-full max-w-[500px] h-auto rounded"></video>
      <div text-sm text-gray-600>fps:{{ fps.toFixed(3) }}</div>
    </div>
    <div flex flex-wrap w-full gap-2 mt-4>
      <div v-for="categorie in categories" :key="categorie.index" class="w-1/2 sm:w-40 p-2 bg-white rounded shadow-sm">
        <div text-sm font-medium>{{ categorie.categoryName }}</div>
        <div text-xs text-gray-500>{{ categorie.score.toFixed(8) }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { FilesetResolver, FaceLandmarker } from '@mediapipe/tasks-vision'
// vues
onMounted(() => {
  init()
  // window.$ObjLargeTemp.set('scene', scene)
})
onBeforeUnmount(() => {
  // scene && scene.dispose()
  // window.$ObjLargeTemp.delete('scene')
})
let categories = ref([]) as any
// 窗口
const width = 500
const height = 500
let faceLandmarker: FaceLandmarker
let video: HTMLVideoElement
async function init() {
  // 1加载MediaPipe模型
  faceLandmarker = await loadMediapipeModels()
  // 2开启摄像头视频流加入landmarker
  streamWebcamThroughFaceLandmarker('videoDom')
}


class FpsShow {
  private fps: number
  private startTime: number
  private frameCount: number
  constructor() {
    this.fps = 0
    this.startTime = Date.now()
    this.frameCount = 0
  }
  update() {
    this.frameCount++
    const currentTime = Date.now()
    const elapsedTime = currentTime - this.startTime
    if (elapsedTime >= 1000) {
      this.fps = this.frameCount / (elapsedTime / 1000)
      this.startTime = currentTime
      this.frameCount = 0
    }
  }
  getFps() {
    return this.fps
  }
}

const fpsShow = new FpsShow()

const fps = ref(0)


/**
 * 1加载MediaPipe模型
 */
async function loadMediapipeModels() {
  // https://www.npmjs.com/package/@mediapipe/tasks-vision?activeTab=readme
  const vision = await FilesetResolver.forVisionTasks(
    // 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.1.0-alpha-16/wasm'
    '/jsLib/mediapipe/tasks-vision-0.10.17/wasm'
  )
  const faceLandmarker = await FaceLandmarker.createFromOptions(
    vision,
    {
      baseOptions: {
        modelAssetPath: "/jsLib/mediapipe/face_landmarker.task",
        delegate: 'GPU'
      },
      runningMode: 'VIDEO',
      outputFaceBlendshapes: true,
      outputFacialTransformationMatrixes: true
    });
  console.log('Loaded MediaPipe模型.')
  return faceLandmarker
}

// 2开启摄像头视频流加入landmarker Stream webcam into landmarker loop (and also make video visible)
async function streamWebcamThroughFaceLandmarker(videoDom: string) {
  video = document.getElementById(videoDom) as HTMLVideoElement
  function onAcquiredUserMedia(stream: MediaStream) {
    video.srcObject = stream
    video.onloadedmetadata = () => {
      video.play()
    }
  }
  try {
    const evt = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: 'user',
        width: width,
        height: height
      }
    })
    onAcquiredUserMedia(evt)
    video.requestVideoFrameCallback(onVideoFrame)
  } catch (e) {
    console.error(`Failed to acquire camera feed: ${e}`)
  }
}
/**
 * 单帧处理
 * @param time
 */
function onVideoFrame(time: any) {
  // 脸特征提取
  detectFaceLandmarks(time)
  video.requestVideoFrameCallback(onVideoFrame)
  fpsShow.update()
  fps.value = fpsShow.getFps()
}

/**
 * 当前帧处理
 * @param {*} time
 * @returns
 */
function detectFaceLandmarks(time: any) {
  // 已加载人脸识别模型
  if (!faceLandmarker) return
  // 对提供的视频帧执行人脸特征点检测
  const landmarks = faceLandmarker.detectForVideo(video, time)
  // 脸部特征点
  const faces = landmarks.faceLandmarks
  // 位置方向
  const transformationMatrices = landmarks.facialTransformationMatrixes
  //识别表情
  const blendshapes = landmarks.faceBlendshapes
  if (blendshapes && blendshapes[0]) categories.value = blendshapes[0].categories as any

  // console.log(blendshapes)
}
</script>
